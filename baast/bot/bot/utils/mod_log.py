import hikari



class ModLogValues:
    info = 0 #20
    warning = 1 #30
    error = 2 #40
    critical = 3 #50
    event = 4

    @classmethod
    def get_color(cls, typ: int) -> hikari.Color:
        color = [
            (0xff, 0xff, 0xff), #info
            (0xf0, 0xa4, 0x5d), #warning
            (0xff, 0x55, 0x55), #error
            (0xb0, 0x09, 0x09), #critical b00909
            (0xf1, 0xef, 0xde), # event f1efde
        ][typ]
        return hikari.Color.from_rgb(color[0], color[1], color[2])