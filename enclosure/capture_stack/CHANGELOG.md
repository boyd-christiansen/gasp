# v1.2 — sculpted water-ripple face

- Reused the author's solid water-impact profile. Preserved its profile functions and included the original source for provenance.
- Centered the ripple at the radar chip, expanded its radii 1.35×, scaled height 0.55×, and blended the edge and four screw lands into the enclosure perimeter. The central spire gives way to the open antenna window.
- Added a separate flat-backed cover, approximately 180 × 180 × 7.65 mm, so the sculpture can print facing up. The structural front remains a separate print with its board posts facing up.
- Replaced the front grille with seven curved vent slots that follow the ripple rings and align through both layers. The slots have rounded ends and are interrupted around support posts and cable access.
- Flared the radar opening outward through the raised cover. The modeled ±60° clearance pyramid remains unobstructed through the full relief height.
- Changed the four outer closure screws to **M3 × 16**. ICBOOST uses M3 × 12, as in v1.1. The revised total is eight M3 × 16 and six M3 × 12 screws; all other hardware counts are unchanged.
- Delivered a fine 0.02 mm STL of the ripple cover and fine GLB previews, checked as closed connected meshes. Refreshed the assembly, exploded, print-layout and rear views.

The rear shell, stand, cable guide, three washer designs and fit coupon are unchanged from v1.1. Their STL files are byte-identical to the v1.1 archive. Use the new structural front and ripple cover together; their vent positions differ from the prior front.

Geometry, component and plug clearances, full nominal fastener engagement, five tilt positions, all nine print meshes, the sampled wave profile and all seven through-vent paths passed the included checks. Physical printing/fit, cable bending, thermal, RF and load performance remain untested. Earlier prototype ZIPs are local development archives, not part of this repository.

# v1.1 — softer enclosure and organized cable routing

- Increased the case's plan-view corner radius to 14 mm. Added a 1.2 mm front perimeter fillet and a 1.5 mm rear perimeter fillet.
- Replaced the front's horizontal grille rows with four concentric radar-wave vents and a smaller waveform grille. Rounded the side vent ends and the lower front connector notch.
- Concealed the four carrier-mounting nuts in side-loading pockets below the front skin. Carrier screws are now **M3 × 12**, not the v1.0 M3 × 16. Added shallow recesses for the four outer closure washers.
- Replaced the angular stand crowns and exposed narrow fins with rounded 18 mm crowns, 1 mm side-edge fillets, continuous tapered heels and rounded lower openings. The base has 20 mm plan-view corners and a 2 mm upper-edge fillet. All five angle markings remain fully engraved inside the side plate.
- Replaced the large top and bottom cable bays with individual rounded ports. Added three more tie stations, for six in total.
- Added a removable cable guide behind the housing. It uses two M3 × 12 screws, two standard nuts and two metal washers.

The board coordinates, PCB support heights, AOP connector spacing, open antenna window, default 20° aim, 0–40° indexed adjustment and 214 × 195 mm desk footprint are preserved. The stand crown is now 138 mm high; the assembled enclosure remains approximately 220.7 mm high at 20°.

Print the v1.1 rear shell, front bezel, table base and cable guide together. Printed washers and the fit coupon are unchanged. The v1.0 ZIP is retained separately; do not mix its carrier screw instructions with the new front.

This remains a prototype. CAD clearance and mesh checks do not establish physical fit, cable bend suitability, thermal performance, RF performance or load strength.
