from lightbulb import components

class SupportButton(components.Menu):
    value = False
    
    def __init__(self):
        self.value = False
        
        self.true = self.add_link_button(
            "https://discord.gg/RNrA9Gtxmm",
            label="Support",
        )