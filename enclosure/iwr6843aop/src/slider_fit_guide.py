"""Assembly illustration of the existing test coupons; not a print plate."""
import build123d as bd
from cadgen import model
import enclosure_v2 as v2


def parts(dy, dz):
    rear = v2.slider_rear_coupon().shape
    front = v2.print_flip(v2.slider_front_coupon().shape, v2.e.FRONT_OUTER)
    rear.color = '#426F91'
    front = bd.Pos(0, dy, dz) * front
    front.color = '#E98A36'
    return rear, front


def arrow(start, direction, length):
    plane = bd.Plane(origin=start, z_dir=direction)
    shaft = bd.Cylinder(.35, length - 2,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    tip = bd.Pos(0, 0, length - 2) * bd.Cone(1.1, 0, 2,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    result = plane * (shaft + tip)
    result.color = '#D04D40'
    return result


def label(text, y):
    plane = bd.Plane(origin=(-8, y, -5), x_dir=(0, -1, 0), z_dir=(-1, 0, 0))
    result = plane * bd.extrude(bd.Text(text, font_size=3.2), amount=.1)
    result.color = '#263949'
    return result


@model
def slider_fit_guide():
    children = []
    for y, dy, dz, title in [(38, -6, 14, '1. LOWER'),
                              (0, -6, 0, '2. SLIDE 6 mm'),
                              (-38, 0, 0, '3. ENGAGED')]:
        rear, front = parts(dy, dz)
        children.extend([bd.Pos(0, y, 0) * rear, bd.Pos(0, y, 0) * front,
                         label(title, y)])
    children.append(arrow((-9, 29, 26), (0, 0, -1), 10))
    children.append(arrow((-9, -8, 17), (0, 1, 0), 8))
    return bd.Compound(children=children, label='slider_fit_instructions_not_for_printing')


if __name__ == '__main__':
    slider_fit_guide()
