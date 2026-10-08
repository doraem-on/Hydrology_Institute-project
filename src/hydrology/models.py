"""All four networks consume only the history available at forecast issue time."""
import math
import torch
from torch import nn

NAMES = ("lstm", "stacked_lstm", "bilstm", "transformer")


class RecurrentForecaster(nn.Module):
    def __init__(self, hidden=32, layers=1, bidirectional=False):
        super().__init__()
        self.bidirectional = bidirectional
        self.rnn = nn.LSTM(3, hidden, num_layers=layers, batch_first=True,
                           bidirectional=bidirectional, dropout=0.1 if layers > 1 else 0)
        self.head = nn.Linear(hidden * (2 if bidirectional else 1), 1)

    def forward(self, x):
        _, (h, _) = self.rnn(x)
        # Both terminal states describe the same historical window.
        encoded = torch.cat((h[-2], h[-1]), dim=1) if self.bidirectional else h[-1]
        return x[:, -1, 0] + self.head(encoded).squeeze(-1)


class TransformerForecaster(nn.Module):
    def __init__(self, hidden=32, lookback=30):
        super().__init__()
        if hidden % 4:
            raise ValueError("Transformer width must be divisible by four heads")
        self.input_projection = nn.Linear(3, hidden)
        positions = torch.arange(lookback).unsqueeze(1)
        frequencies = torch.exp(torch.arange(0, hidden, 2) * (-math.log(10000.0) / hidden))
        encoding = torch.zeros(lookback, hidden)
        encoding[:, 0::2] = torch.sin(positions * frequencies)
        encoding[:, 1::2] = torch.cos(positions * frequencies)
        self.register_buffer("position", encoding.unsqueeze(0))
        layer = nn.TransformerEncoderLayer(hidden, 4, hidden * 2, dropout=0.1, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, 2, enable_nested_tensor=False)
        # Independent initial weights across the cloned encoder layers.
        for layer in self.encoder.layers:
            for parameter in layer.parameters():
                if parameter.ndim > 1:
                    nn.init.xavier_uniform_(parameter)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        history = self.input_projection(x) + self.position[:, :x.shape[1]]
        return x[:, -1, 0] + self.head(self.encoder(history)[:, -1]).squeeze(-1)


def build_model(name, hidden=32, lookback=30):
    if name == "lstm":
        return RecurrentForecaster(hidden)
    if name == "stacked_lstm":
        return RecurrentForecaster(hidden, layers=2)
    if name == "bilstm":
        return RecurrentForecaster(hidden, bidirectional=True)
    if name == "transformer":
        return TransformerForecaster(hidden, lookback)
    raise ValueError(f"Unknown model: {name}")
