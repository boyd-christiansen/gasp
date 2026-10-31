# Enclosure hardware — v1.2

For one enclosure with **both interchangeable fronts equipped with inserts**. You reuse the same cover screws when swapping fronts. The PCB standoffs are printed into the rear shell; no separate standoffs are needed.

| Buy at least | Part / search phrase | Required dimensions | Used for |
|---|---|---|---|
| 1 | **¼″-20 UNC standard hex nut** | 7/16″ across flats (11.11 mm), about 7/32″ thick (5.56 mm); plain full-height hex | Microphone-arm mount |
| 4 | **M2.5-0.45 × 16 mm button-head machine screws** | Head diameter ≤5.2 mm; stainless or plated steel | Close the enclosure |
| 8 | **M2.5 brass heat-set inserts, 4 mm long × 3.5 mm OD** | Often written `M2.5 × 4 × 3.5` in thread × length × OD order | Four in each front |
| 4 | **M2-0.4 × 6 mm machine screws** | Button or low-profile pan heads; PCB heads ≤4.5 mm diameter | Two for PCB, two for nut retainer |
| 4 | **M2 brass heat-set inserts, 4 mm long × 3.2 mm OD** | Often written `M2 × 4 × 3.2` in thread × length × OD order | Two PCB posts and two retainer holes |
| 2, print these | **Included PCB washers** | Ø4.4 OD × Ø2.3 bore × 0.6 thick; print `exports_v1_2/washer_print_pair.stl` | Under PCB screw heads |
| 1 | **Standard nylon cable tie** | 2.5 mm wide; 150 mm long or longer | USB strain relief in the revised rear shell |

If equipping only one front, four M2.5 inserts are enough. Buying small packs gives you spares.

## Insert purchasing references

The outside diameter matters as much as the thread size. The CAD receiving holes are Ø3.0 mm for the M2 inserts and Ø3.3 mm for the M2.5 inserts. [3D Printer Gear's product dimension table](https://www.3dprintergear.com.au/m2.5-brass-threaded-heat-set-insert) lists those exact insert families and matching recommended hole sizes. Select length 4 mm.

This [Florida Tools insert assortment](https://www.florida.tools/products/350pcs-metric-threaded-inserts-for-plastic-heat-set-insert-knurled-nut-insert-threaded-brass-insert-assortment-kit) lists both `M2 × 4 × 3.2` and `M2.5 × 4 × 3.5`, with 26 of each. It contains more than needed; individual bags with the same dimensions also work. Listings checked 2026-10-30; shipping and live availability are not guaranteed.

The printed bores still need a trial fit for your filament and printer. Standard larger-bodied inserts with the same M2 or M2.5 thread designation need different receiving holes.

## Reuse or buy only if needed

- Your straight USB data cable. The enclosure reserves an 11 × 20 × 6 mm plug boot and a Ø4.4 mm cable.
- The board's existing heatsink.
- A microphone arm ending in a **male ¼″-20 stud**, preferably with 6–8 mm of projecting thread and a shoulder diameter up to 25 mm. If the arm has a 3/8″ or 5/8″ fitting, buy an adapter with a female end matching the arm and a male ¼″-20 output.

## Assembly tools

- Temperature-controlled soldering iron with an M2/M2.5 heat-set insert tip.
- Drivers matching the screw heads you buy; small metric hex keys for hex-socket button heads.
- Calipers and small flush cutters for checking fits and trimming the tie.

Hardware dimensions are nominal prototype requirements. Hand-tighten the arm and shell screws. Full assembly steps and print orientation notes are in [the v1.2 guide](README_v1_2.md).

Compatible alternatives include M2.5 socket-cap heads up to Ø4.35 × 2.35 mm, which fit the Ø5.2 mm rear recess with approximately 0.85 mm projection, and M2 × 6 screws with flat-bearing, low-profile Ø3.8 mm heads. Check actual head dimensions before assembly.
