import AppKit
import SwiftUI

// Uses the same logo, particle field and dissolve envelope as logo-particles.js.
struct LogoParticle {
    let x: Double, y: Double, seed: Double, alpha: Double, dx: Double, dy: Double
}
struct FaceMark: View {
    var active: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private static let image: NSImage? = {
        guard let url = Bundle.main.url(forResource:"face-open",withExtension:"png") else { return nil }
        return NSImage(contentsOf:url)
    }()
    private static let points: [LogoParticle] = {
        guard let image,
              let source = NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:144,pixelsHigh:144,
                bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,
                colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0),
              let graphics = NSGraphicsContext(bitmapImageRep:source) else { return [] }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = graphics
        graphics.imageInterpolation = .high
        image.draw(in:NSRect(x:0,y:0,width:144,height:144))
        NSGraphicsContext.restoreGraphicsState()
        var points: [LogoParticle] = []
        for y in stride(from:0,to:144,by:2) { for x in stride(from:0,to:144,by:2) {
            let alpha = Double(source.colorAt(x:x,y:y)?.alphaComponent ?? 0)
            if alpha < 0.14 { continue }
            func random(_ value: Double) -> Double { value-floor(value) }
            let seed = random(sin(Double(x)*127.1+Double(y)*311.7)*43758.5453123)
            let radius = sqrt(random(sin(Double(x)*269.5+Double(y)*183.3)*43758.5453123))*0.42
            let angle = seed*Double.pi*2, px = (Double(x)+0.5)/144, py = (Double(y)+0.5)/144
            points.append(LogoParticle(x:px,y:py,seed:seed,alpha:alpha,
                dx:0.5+cos(angle)*radius-(0.06+0.88*px),
                dy:0.48+sin(angle)*radius*1.05-(0.06+0.88*py)))
        }}
        return points
    }()
    private static func smooth(_ a: Double, _ b: Double, _ value: Double) -> Double {
        let t = min(1,max(0,(value-a)/(b-a)))
        return t*t*(3-2*t)
    }
    @State private var started = Date()
    var body: some View {
        TimelineView(.animation(minimumInterval:1.0/30,paused:!active || reduceMotion)) { timeline in
            Canvas { context, size in
                let elapsed = max(0,timeline.date.timeIntervalSince(started))
                let phase = active && !reduceMotion ? elapsed.truncatingRemainder(dividingBy:4.2)/4.2 : 0
                let spread = Self.smooth(0.17,0.44,phase)*(1-Self.smooth(0.56,0.88,phase))
                let width = min(size.width,size.height)
                let rect = CGRect(x:width*0.06,y:width*0.06,width:width*0.88,height:width*0.88)
                if let image = Self.image {
                    var mark = context.resolve(Image(nsImage:image))
                    mark.shading = .color(.white)
                    context.opacity = 1-Self.smooth(0,0.28,spread)
                    context.draw(mark,in:rect)
                }
                context.opacity = Self.smooth(0,0.24,spread)*(1-0.24*spread)
                if context.opacity > 0 {
                    var path = Path()
                    for p in Self.points {
                        let curl = sin(elapsed*1.8+p.seed*Double.pi*2)*0.012*spread
                        let x = width*(0.06+0.88*p.x+spread*p.dx+curl)
                        let y = width*(0.06+0.88*p.y+spread*p.dy)
                        let r = width*(0.0048+0.0018*p.seed)
                        path.addEllipse(in:CGRect(x:x-r,y:y-r,width:r*2,height:r*2))
                    }
                    context.fill(path,with:.color(.white))
                }
            }
        }.frame(width:54,height:54).accessibilityHidden(true)
         .onChange(of:active) { value in if value { started = Date() } }
    }
}
