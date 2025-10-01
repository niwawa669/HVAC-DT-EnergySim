import torch


class CVAlgorithm:
    
    def __init__(self):
        # 生成遍历计算输入数据：
        self.Freq_range = [265.0, 327.0]
        self.trchw_range = [6.0, 14.0]   # chilled water,chw; temperature_return, tr; temperature_supply, ts
        self.trcw_range = [12.0, 40.0]   # cooling water, cw
        self.G_range = [0.2, 1.0]

        self.Qr = 2285.0  # 额定制冷量，kW
        self.Qcr = 2285.0 * (1.0 + 1.0 / 6.78)
        self.Grchw = self.Qr * 0.172 / 3.6
        self.Grcw = self.Qcr * 0.172 / 3.6
        self.Gchw_range = [self.Grchw * self.G_range[0], self.Grchw]
        self.Gcw_range = [self.Grcw * self.G_range[0], self.Grcw]