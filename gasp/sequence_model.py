"""Optional PyTorch sentence recipe; imported only by the training worker.

This first encoder uses saved complex frames, not raw within-chirp ADC. There is
no temporal downsampling, audio input, language model, or prompt-conditioned decode.
"""
import json
import os

import numpy as np

from .learning_data import digest, normalize_text, signal
from .learning_models import metrics
from .storage import atomic_json


VOCAB = " abcdefghijklmnopqrstuvwxyz0123456789'"


def sequence_features(root, row, recipe):
    z, t = signal(root, row)
    step = row["profile"]["range_step_m"]
    lo = max(0, int(np.ceil(recipe["range_min_m"] / step)))
    hi = min(z.shape[1], int(np.floor(recipe["range_max_m"] / step)) + 1)
    if hi-lo < 2:
        raise ValueError("The radar range gate has fewer than two bins")
    # Spatial interpolation only. Preserve real frames and each inter-frame interval.
    positions = np.linspace(lo, hi-1, 16)
    left = np.floor(positions).astype(int); right = np.ceil(positions).astype(int)
    weights = (positions-left)[None, :, None]
    z = z[:, left, :] * (1-weights) + z[:, right, :] * weights
    magnitude = np.log1p(np.abs(z))
    magnitude -= np.median(magnitude, axis=0, keepdims=True)
    delta = np.zeros_like(z)
    delta[1:] = z[1:] * z[:-1].conj()
    phase = np.angle(delta)
    strength = np.abs(delta)
    reliability = strength / (strength + np.median(strength)*.05 + 1e-6)
    dt = np.r_[0, np.diff(t)/1e9]
    typical = max(float(np.median(dt[1:])), 1e-6)
    reliability[dt > 2*typical] = 0  # Never bridge a dropped-frame phase discontinuity.
    result = np.concatenate([magnitude.reshape(len(z), -1),
        (np.sin(phase)*reliability).reshape(len(z), -1),
        (np.cos(phase)*reliability).reshape(len(z), -1),
        np.clip(dt/typical, 0, 10)[:, None]], axis=1).astype(np.float32)
    if not np.isfinite(result).all():
        raise ValueError("Non-finite sequence features")
    return result


def targets(text):
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("No supported English text remains after normalization")
    return [VOCAB.index(c)+1 for c in normalized]


def minimum_ctc_frames(tokens):
    return len(tokens) + sum(a == b for a, b in zip(tokens, tokens[1:]))


def runtime():
    try:
        import torch
    except ImportError as exc:
        raise ValueError("The sentence worker needs the training extra (PyTorch). Run it in the pinned training environment.") from exc
    torch.set_num_threads(min(8, max(1, int(os.environ.get("SLURM_CPUS_PER_TASK", "2")))))
    if torch.cuda.is_available():
        if not os.environ.get("SLURM_JOB_ID"):
            raise ValueError("GPU training must run inside a Slurm allocation")
        return torch, torch.device("cuda")
    return torch, torch.device("cpu")


def network(torch, input_size, hidden_size):
    class RadarCTC(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.front = torch.nn.Sequential(torch.nn.Conv1d(input_size, hidden_size, 3, padding=1),
                torch.nn.GELU(), torch.nn.Conv1d(hidden_size, hidden_size, 3, padding=1), torch.nn.GELU())
            self.encoder = torch.nn.GRU(hidden_size, hidden_size, num_layers=2, batch_first=True, bidirectional=True)
            self.output = torch.nn.Linear(hidden_size*2, len(VOCAB)+1)

        def forward(self, x, lengths):
            x = x.transpose(1, 2)
            valid = (torch.arange(x.shape[-1], device=x.device)[None, :] < lengths.to(x.device)[:, None])[:, None, :]
            # Convolution biases must not turn padding into a neighbor's input.
            # A short take should produce the same logits alone or in a long batch.
            for layer in self.front:
                x = layer(x) * valid
            x = x.transpose(1, 2)
            packed = torch.nn.utils.rnn.pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
            x, _ = self.encoder(packed)
            x, _ = torch.nn.utils.rnn.pad_packed_sequence(x, batch_first=True)
            return self.output(x).log_softmax(-1)
    return RadarCTC()


def batch(torch, arrays, device):
    lengths = torch.tensor([len(a) for a in arrays], dtype=torch.long)
    padded = torch.nn.utils.rnn.pad_sequence([torch.from_numpy(a) for a in arrays], batch_first=True)
    return padded.to(device), lengths


def decode(log_probs, lengths):
    paths = log_probs.argmax(-1).cpu().tolist()
    result = []
    for path, length in zip(paths, lengths):
        previous = 0; text = []
        for token in path[:int(length)]:
            if token and token != previous:
                text.append(VOCAB[token-1])
            previous = token
        result.append(" ".join("".join(text).split()))
    return result


def save_weights(model, out, config):
    # Portable, non-executable artifacts. The app never unpickles imported weights.
    np.savez_compressed(out / "model.npz", **{k: v.detach().cpu().float().numpy() for k, v in model.state_dict().items()})
    atomic_json(out / "model.json", config)


def fit_sequence(snapshot, root, out, notify, check):
    torch, device = runtime()
    recipe = snapshot["recipe"]
    torch.manual_seed(recipe["seed"])
    rng = np.random.default_rng(recipe["seed"])
    rows = [r for r in snapshot["rows"] if r["split"] == "train"]
    dev = [r for r in snapshot["rows"] if r["split"] == "validation" and r["articulation"] == "silent"]
    input_size = None
    # Validate every training target before allocating a model; never zero impossible losses.
    for i, row in enumerate(rows):
        check(); x = sequence_features(root, row, recipe)
        if len(x) < minimum_ctc_frames(targets(row["text"])):
            raise ValueError(f"Not enough measured frames for the transcript in take {row['trial_id']}. Inspect timing or use a higher-rate acquisition profile.")
        if input_size is not None and x.shape[1] != input_size:
            raise ValueError("Incompatible radar channel layout")
        input_size = x.shape[1]
        notify("preparing", completed=i+1, total=len(rows))
    model = network(torch, input_size, recipe["hidden_size"]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=recipe["learning_rate"], weight_decay=.0001)
    loss_fn = torch.nn.CTCLoss(blank=0, zero_infinity=False)
    config = dict(task="sentences", recipe=recipe, input_size=input_size, vocab=VOCAB,
                  torch_version=str(torch.__version__), decoder="greedy-radar-only-v1")
    checkpoint = out / "resume.pt"
    start, best = 0, float("inf")
    identity = digest(snapshot)
    if checkpoint.exists():
        saved = torch.load(checkpoint, map_location=device, weights_only=True)
        if saved["dataset"] != identity:
            raise ValueError("Checkpoint belongs to a different dataset")
        model.load_state_dict(saved["model"]); optimizer.load_state_dict(saved["optimizer"])
        start, best = saved["epoch"], saved["best"]
        rng.bit_generator.state = saved["rng"]
        torch.set_rng_state(saved["torch_rng"].cpu())
        if device.type == "cuda" and saved.get("cuda_rng") is not None:
            torch.cuda.set_rng_state_all(saved["cuda_rng"])
    for epoch in range(start, recipe["epochs"]):
        check(); model.train(); losses = []
        order = rng.permutation(len(rows))
        for offset in range(0, len(rows), recipe["batch_size"]):
            check()
            chosen = [rows[int(i)] for i in order[offset:offset+recipe["batch_size"]]]
            x, lengths = batch(torch, [sequence_features(root, r, recipe) for r in chosen], device)
            labels = [targets(r["text"]) for r in chosen]
            y = torch.tensor([t for sequence in labels for t in sequence], dtype=torch.long, device=device)
            label_lengths = torch.tensor([len(t) for t in labels], dtype=torch.long)
            optimizer.zero_grad(set_to_none=True)
            output = model(x, lengths)
            loss = loss_fn(output.transpose(0, 1), y, lengths, label_lengths)
            if not torch.isfinite(loss):
                raise ValueError("CTC produced a non-finite loss; this run is not valid")
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step(); losses.append(float(loss.detach()))
            notify("training", epoch=epoch+1, epochs=recipe["epochs"], completed=min(offset+len(chosen), len(rows)),
                   total=len(rows), loss=float(np.mean(losses)))
        model.eval(); predictions = []
        with torch.no_grad():
            for row in dev:
                check(); x, lengths = batch(torch, [sequence_features(root, row, recipe)], device)
                predictions.append(dict(expected=row["text"], predicted=decode(model(x, lengths), lengths)[0]))
        measured = metrics("sentences", predictions)
        score = measured["wer"] if measured else float(np.mean(losses))
        if score < best:
            best = score; save_weights(model, out, config)
        notify("training", epoch=epoch+1, epochs=recipe["epochs"], loss=float(np.mean(losses)),
               development_wer=measured["wer"] if measured else None, checkpoint=True)
        tmp = out / "resume.tmp"
        torch.save(dict(dataset=identity, epoch=epoch+1, best=best, model=model.state_dict(),
            optimizer=optimizer.state_dict(), rng=rng.bit_generator.state, torch_rng=torch.get_rng_state(),
            cuda_rng=torch.cuda.get_rng_state_all() if device.type == "cuda" else None), tmp)
        tmp.replace(checkpoint)


def predict(snapshot, root, out, rows, notify, check):
    torch, device = runtime()
    config = json.loads((out / "model.json").read_text())
    if config["vocab"] != VOCAB:
        raise ValueError("Unsupported model vocabulary")
    model = network(torch, config["input_size"], config["recipe"]["hidden_size"]).to(device)
    with np.load(out / "model.npz", allow_pickle=False) as weights:
        model.load_state_dict({k: torch.from_numpy(weights[k]).to(device) for k in weights.files}, strict=True)
    model.eval(); result = []
    with torch.no_grad():
        for i, row in enumerate(rows):
            check(); x, lengths = batch(torch, [sequence_features(root, row, config["recipe"])], device)
            result.extend(decode(model(x, lengths), lengths))
            notify("evaluating", completed=i+1, total=len(rows))
    return result
