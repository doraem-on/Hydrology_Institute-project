# Algorithms and working principles

## Shared forecasting task

Let Q(t) be daily mean discharge in m³/s. The experiment predicts Q(t) from
observations through t−1. A 30-day window contains standardized log1p(Q), sine
of annual phase and cosine of annual phase. Training-period statistics alone
define standardization. A linear output head predicts the change from the
last standardized log-flow value. This residual formulation makes persistence
a useful reference point for every architecture.

The networks minimize mean squared error in standardized log1p discharge.
This gives proportionally more attention to lower flows than an untransformed
discharge loss. Final metrics are calculated in m³/s. A calibration-period
smearing factor converts each network's log forecast to an approximate mean
discharge; simply exponentiating a log forecast is not generally a mean.

## LSTM

An LSTM carries a cell state and a hidden state through the history. Gates
control what is retained, written and exposed. In the modern formulation,

```
i_t = sigmoid(W_i [x_t, h_(t-1)] + b_i)
f_t = sigmoid(W_f [x_t, h_(t-1)] + b_f)
o_t = sigmoid(W_o [x_t, h_(t-1)] + b_o)
g_t = tanh(W_g [x_t, h_(t-1)] + b_g)
c_t = f_t * c_(t-1) + i_t * g_t
h_t = o_t * tanh(c_t)
```

The cell state provides a route for carrying information across multiple
steps. In this implementation one recurrent layer with 32 hidden units
encodes the observed history. Its final hidden state feeds a linear head.
See [Hochreiter and Schmidhuber (1997)](https://www.bioinf.jku.at/publications/older/2604.pdf)
for the original LSTM and [PyTorch's LSTM equations](https://docs.pytorch.org/docs/stable/generated/torch.nn.modules.rnn.LSTM.html)
for the implemented modern gates.

## Stacked LSTM

Two LSTM layers are placed vertically: the sequence of hidden outputs from
layer one becomes the sequence of inputs to layer two. Each layer has its
own temporal state. The upper layer can learn features of lower-layer
patterns. Extra depth increases capacity and optimization cost, and does
not guarantee better generalization. Here both layers have width 32, with
dropout between layers. Stacking refers to network depth, not averaging
separately trained predictions. [PyTorch LSTM](https://docs.pytorch.org/docs/stable/generated/torch.nn.modules.rnn.LSTM.html)
documents the multi-layer operation.

## Bidirectional LSTM

One LSTM reads the historical window oldest-to-newest and another reads that
same window newest-to-oldest. Their terminal hidden states are concatenated
before prediction. This provides two descriptions of an already observed
history. It is valid here because neither direction sees the target day.
Running a backward network over the entire train-and-test series would leak
future information and is not done. The code uses both final states from
`h_n`, since the last sequence output does not contain the final reverse
state. [PyTorch LSTM documentation](https://docs.pytorch.org/docs/stable/generated/torch.nn.modules.rnn.LSTM.html)
explains that distinction.

## Transformer

Self-attention compares projected queries and keys to weight value vectors:

```
Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V
```

Here Q denotes an attention query matrix, not discharge. Multiple heads can
represent different relationships among historical days. Positional encoding
preserves order; feed-forward blocks transform the attended representations.
See [Vaswani et al. (2017)](https://arxiv.org/abs/1706.03762).

This benchmark uses two encoder layers, four heads, width 32, sinusoidal
positions and the last token's representation. Attention spans only the
past 30 days, so no within-history causal mask is needed for a single target
after that window. It is not an autoregressive decoder or an LLM. Encoder
layer matrices are initialized separately, addressing the initialization
warning in [PyTorch TransformerEncoder](https://docs.pytorch.org/docs/2.14/generated/torch.nn.modules.transformer.TransformerEncoder.html).

## Forecast Bayesian model averaging

Following the forecast-calibration approach of
[Raftery et al. (2005)](https://journals.ametsoc.org/view/journals/mwre/133/5/mwr2906.1.xml),
the implementation combines predictive distributions. For z = log1p(Q),

```
p(z | forecasts) = sum_k w_k Normal(z; a_k + b_k f_k, sigma²)
w_k >= 0, sum_k w_k = 1
```

On the calibration partition, least squares estimates a_k and b_k.
Expectation-maximization estimates the weights and shared residual variance.
Its E step computes component responsibilities, and its M step updates
weights and variance. Log-sum-exp prevents numerical underflow. Weights
reflect relative density fit, not inverse RMSE. The method is empirical
forecast BMA, not full Bayesian integration over neural-network parameters.

Our implementation maps the fitted mixture to nonnegative flow using
Q = max(exp(z)−1, 0). It calculates the exact mean of this transformed
distribution and obtains interval endpoints by inverting its mixture CDF.
Negative latent values produce a point mass at zero. Calibration does not
guarantee coverage under new conditions, so empirical coverage and interval
width are reported on the test partition.

## How to interpret comparisons

Persistence predicts tomorrow's flow as today's flow. Equal averaging uses
the arithmetic mean of the four corrected point forecasts. Both are necessary
controls: a complicated ensemble must demonstrate value against simpler
options. RMSE emphasizes large errors, MAE measures typical absolute error,
NSE compares squared error against the observed-period mean, and KGE (2009
definition) combines correlation, variability ratio and mean ratio. Report
all of them rather than selecting whichever favors the ensemble.

The first run uses one station, one seed, one lead time and a small training
budget. It cannot establish that an architecture is universally best. Future
comparisons should fix tuning budgets in advance, retain untouched test
periods, use multiple seeds and catchments, and examine flood peaks and low
flows separately. Rainfall and temperature predictors should be added only
when their availability at forecast issue time is established.
