from flexx import flx


class MyImage(flx.CanvasWidget):
    def init(self):
        self.ctx = self.node.getContext('2d')

    @flx.reaction('size')
    def update(self):
        width, height = self.size
        print(f"{width}/{height}")
        ctx = self.ctx
        ctx.strokeStyle = '#0000ff'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(0, 0)
        ctx.lineTo(width, height)
        ctx.stroke()
        ctx.moveTo(0, height)
        ctx.lineTo(width, 0)
        ctx.stroke()
        ctx.strokeRect(0, 0, width, height)