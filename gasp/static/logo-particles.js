'use strict';
// Sample the existing logo's alpha mask; no alternate face artwork is involved.
window.GaspLogoParticles = class {
  constructor(element) {
    this.element = element;
    this.image = element.querySelector('img');
    this.canvas = element.querySelector('canvas');
    this.context = this.canvas.getContext('2d');
    this.mode = 'idle'; this.phase = 0; this.elapsed = 0; this.frame = 0;
    this.visible = false; this.lastTick = 0; this.lastPaint = 0;
    this.motion = matchMedia('(prefers-reduced-motion: reduce)');
    this.tick = this.tick.bind(this);
    this.motion.addEventListener('change', () => this.refresh());
    document.addEventListener('visibilitychange', () => this.refresh());
    this.observer = new IntersectionObserver(entries => {
      this.visible = entries[0].isIntersecting; this.refresh();
    });
    this.observer.observe(element);
    new ResizeObserver(() => { this.resize(); this.refresh(); }).observe(element);
    if (this.image.complete && this.image.naturalWidth) this.prepare();
    else this.image.addEventListener('load', () => this.prepare(), {once:true});
  }
  static smooth(a, b, value) {
    const t = Math.max(0, Math.min(1, (value-a)/(b-a)));
    return t*t*(3-2*t);
  }
  prepare() {
    if (!this.context) return;
    const mask = document.createElement('canvas'); mask.width = mask.height = 144;
    const ctx = mask.getContext('2d', {willReadFrequently:true});
    ctx.drawImage(this.image, 0, 0, 144, 144);
    const rgba = ctx.getImageData(0, 0, 144, 144).data;
    this.points = [];
    for (let y=0; y<144; y+=2) for (let x=0; x<144; x+=2) {
      const alpha = rgba[(y*144+x)*4+3]/255;
      if (alpha < .14) continue;
      const random = value => value-Math.floor(value);
      const seed = random(Math.sin(x*127.1+y*311.7)*43758.5453123);
      const radius = Math.sqrt(random(Math.sin(x*269.5+y*183.3)*43758.5453123))*.42;
      const angle = seed*Math.PI*2, px = (x+.5)/144, py = (y+.5)/144;
      this.points.push({x:px,y:py,seed,alpha,
        dx:.5+Math.cos(angle)*radius-(.06+.88*px),
        dy:.48+Math.sin(angle)*radius*1.05-(.06+.88*py)});
    }
    this.resize(); this.refresh();
  }
  resize() {
    const size = this.element.clientWidth;
    if (!size) return;
    this.size = size;
    const scale = Math.min(2, window.devicePixelRatio || 1);
    this.canvas.width = this.canvas.height = Math.round(size*scale);
    this.context?.setTransform(scale, 0, 0, scale, 0, 0);
  }
  setMode(mode) {
    if (this.mode === mode) return;
    this.mode = mode; this.refresh();
  }
  refresh() {
    if (!this.points || !this.size) return;
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0; this.lastTick = 0;
    if (!this.visible || document.hidden) return;
    if (this.motion.matches) { this.draw(0, 0); return; }
    this.frame = requestAnimationFrame(this.tick);
  }
  tick(now) {
    this.frame = 0;
    if (!this.visible || document.hidden) return;
    const dt = this.lastTick ? Math.min(.05, (now-this.lastTick)/1000) : 0;
    this.lastTick = now; this.elapsed += dt;
    // Let the current dissolve finish when saving, then keep the complete mark.
    if (this.mode === 'still') {
      if (this.phase > 0 && this.phase < .9) this.phase = Math.min(.9, this.phase+dt/2.2);
      else this.phase = 0;
    } else this.phase = (this.phase+dt/(this.mode === 'active' ? 4.2 : 6.4))%1;
    if (now-this.lastPaint >= 1000/30 || !this.lastPaint) {
      this.draw(this.phase, this.elapsed); this.lastPaint = now;
    }
    if (this.mode !== 'still' || this.phase !== 0) this.frame = requestAnimationFrame(this.tick);
    else this.draw(0, 0);
  }
  draw(phase, elapsed=0) {
    if (!this.points || !this.size) return;
    const smooth = window.GaspLogoParticles.smooth;
    const spread = smooth(.17,.44,phase)*(1-smooth(.56,.88,phase));
    const size = this.size, ctx = this.context;
    ctx.clearRect(0,0,size,size);
    ctx.globalAlpha = 1-smooth(0,.28,spread);
    ctx.drawImage(this.image,size*.06,size*.06,size*.88,size*.88);
    ctx.globalAlpha = smooth(0,.24,spread)*(1-.24*spread);
    if (ctx.globalAlpha > 0) {
      ctx.fillStyle = getComputedStyle(this.element).color;
      ctx.beginPath();
      for (const p of this.points) {
        const curl = Math.sin(elapsed*1.8+p.seed*Math.PI*2)*.012*spread;
        const x = size*(.06+.88*p.x+spread*p.dx+curl);
        const y = size*(.06+.88*p.y+spread*p.dy);
        const radius = size*(.0048+.0018*p.seed);
        ctx.moveTo(x+radius,y);ctx.arc(x,y,radius,0,Math.PI*2);
      }
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    this.element.dataset.particlesReady = 'true';
  }
};
