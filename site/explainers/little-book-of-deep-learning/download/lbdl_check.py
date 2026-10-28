"""Every number in "The Little Book of Deep Learning: an explainer", recomputed.

Run: python3 lbdl_check.py   (needs numpy)
Each check asserts; the printed values are the ones quoted in the text.
"""
import numpy as np

np.set_printoptions(precision=4, suppress=True)


def softmax(f):
    e = np.exp(f - f.max())          # shifting by the max changes nothing (section 2) and avoids overflow
    return e / e.sum()


def show(name, value):
    print(f"{name}: {value}")


# --- 1. exp -------------------------------------------------------------------------------------
series = sum(1.0 / np.prod(np.arange(1, k + 1)) for k in range(20))   # sum of 1/k!, k = 0..19
assert abs(series - np.e) < 1e-12
show("exp at 0, 1, 2, -1, 10", np.exp([0, 1, 2, -1, 10]).round(2))

# --- 2. softmax ---------------------------------------------------------------------------------
f = np.array([2.0, 1.0, 0.0])
show("exp(2, 1, 0)", np.exp(f).round(2))
show("sum", np.exp(f).sum().round(2))
p = softmax(f)
show("softmax(2, 1, 0)", p.round(3))
assert np.allclose(softmax(f + 100), p)                                 # adding a constant: no change
assert np.isclose(p[0] / p[1], np.e)                                   # a gap of 1 = ratio e
show("softmax(10 * logits)", [f"{v:.2g}" for v in softmax(10 * f)])

# --- 3. cross-entropy ---------------------------------------------------------------------------
show("loss if true class is first", round(-np.log(p[0]), 2))
show("loss if true class is third", round(-np.log(p[2]), 2))
y = 0
lce = -f[y] + np.log(np.exp(f).sum())                                 # the simplified form
assert np.isclose(lce, -np.log(p[y]))
show("ln 50000 (uniform guess over 50k tokens)", round(np.log(50_000), 2))

# gradient of the loss with respect to the logits = p - onehot(y), checked by finite differences
def ce(f, y):
    return -np.log(softmax(f)[y])

eps = 1e-6
fd = np.array([(ce(f + eps * np.eye(3)[i], y) - ce(f - eps * np.eye(3)[i], y)) / (2 * eps) for i in range(3)])
assert np.allclose(fd, p - np.eye(3)[y], atol=1e-8)
show("dL/df (predicted minus target)", (p - np.eye(3)[y]).round(3))

# --- 4. triplet loss ----------------------------------------------------------------------------
triplet = lambda d_pos, d_neg: max(0.0, 1 - d_neg + d_pos)
assert triplet(0.5, 2.0) == 0.0
assert np.isclose(triplet(0.8, 1.2), 0.6)

# --- 5. the tiny backprop example ---------------------------------------------------------------
x, w1, w2, t = 2.0, 3.0, 4.0, 20.0
h = w1 * x; yv = w2 * h; e = yv - t; loss = e ** 2
assert (h, yv, e, loss) == (6, 24, 4, 16)
dl_de = 2 * e; dl_dy = dl_de * 1; dl_dw2 = dl_dy * h; dl_dh = dl_dy * w2; dl_dw1 = dl_dh * x; dl_dx = dl_dh * w1
assert (dl_de, dl_dy, dl_dw2, dl_dh, dl_dw1, dl_dx) == (8, 8, 48, 32, 64, 96)

def tiny(w1, w2):
    return (w2 * w1 * x - t) ** 2

show("loss with w2 = 4.01", round(tiny(3, 4.01), 4))
show("loss with w1 = 3.01", round(tiny(3.01, 4), 4))
w2n, w1n = 4 - 0.001 * 48, 3 - 0.001 * 64
show("after one step: w1, w2, h, y, loss", (round(w1n, 3), round(w2n, 3), round(w1n * x, 3),
                                           round(w2n * w1n * x, 3), round(tiny(w1n, w2n), 2)))
show("0.9**50, 1.1**50", (round(0.9 ** 50, 4), round(1.1 ** 50, 1)))

# --- 6. Jacobians -------------------------------------------------------------------------------
# 6a. The softmax Jacobian is diag(p) - p p^T; it is symmetric and sends the all-ones vector to 0.
J_soft = np.diag(p) - np.outer(p, p)
fd_J = np.column_stack([(softmax(f + eps * np.eye(3)[j]) - softmax(f - eps * np.eye(3)[j])) / (2 * eps)
                        for j in range(3)])
assert np.allclose(J_soft, fd_J, atol=1e-8)
assert np.allclose(J_soft, J_soft.T) and np.allclose(J_soft @ np.ones(3), 0)
show("softmax Jacobian at (2, 1, 0)\n", J_soft.round(3))
g_p = -np.eye(3)[y] / p[y]                     # gradient of -log p_y with respect to p
assert np.allclose(J_soft.T @ g_p, p - np.eye(3)[y])

# 6b. A two-layer network: x (3) -> linear (4) -> ReLU -> linear (3 logits) -> cross-entropy.
# Small integers, so every matrix can be followed by hand.
x = np.array([1.0, 2.0, -1.0])
W1 = np.array([[1, 1, 0], [0, 1, 1], [1, -1, 0], [-1, 0, 1]], dtype=float); b1 = np.zeros(4)
W2 = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [-1, 1, 1, 1]], dtype=float); b2 = np.zeros(3)
y = 1                      # the true class is the second one

z1 = W1 @ x + b1           # (4,)
a1 = np.maximum(z1, 0)     # (4,)
z2 = W2 @ a1 + b2          # (3,) logits
p2 = softmax(z2)
loss = -np.log(p2[y])
show("z1", z1); show("a1", a1); show("logits", z2); show("p", p2); show("loss", round(loss, 4))

# Every Jacobian built explicitly, then multiplied: the chain rule, literally.
J_loss = (p2 - np.eye(3)[y])[None, :]          # 1 x 3: loss with respect to logits
J_lin2 = W2                                    # 3 x 4: logits with respect to a1
J_relu = np.diag((z1 > 0).astype(float))       # 4 x 4: a1 with respect to z1 (diagonal)
J_lin1 = W1                                    # 4 x 3: z1 with respect to x
J_total = J_loss @ J_lin2 @ J_relu @ J_lin1    # 1 x 3: loss with respect to x
show("J_relu diagonal", np.diag(J_relu))

# Backprop: never form a Jacobian, only vector-Jacobian products, right to left.
g_z2 = p2 - np.eye(3)[y]
g_W2 = np.outer(g_z2, a1); g_a1 = W2.T @ g_z2
g_z1 = g_a1 * (z1 > 0)
g_W1 = np.outer(g_z1, x);  g_x = W1.T @ g_z1
assert np.allclose(J_total.ravel(), g_x)

# Finite differences on every input and every weight.
def net_loss(x, W1, W2):
    return -np.log(softmax(W2 @ np.maximum(W1 @ x + b1, 0) + b2)[y])

def fd_grad(fun, arr):
    g = np.zeros_like(arr)
    for i in np.ndindex(arr.shape):
        d = np.zeros_like(arr); d[i] = eps
        g[i] = (fun(arr + d) - fun(arr - d)) / (2 * eps)
    return g

assert np.allclose(fd_grad(lambda v: net_loss(v, W1, W2), x), g_x, atol=1e-6)
assert np.allclose(fd_grad(lambda M: net_loss(x, M, W2), W1), g_W1, atol=1e-6)
assert np.allclose(fd_grad(lambda M: net_loss(x, W1, M), W2), g_W2, atol=1e-6)
show("gradient with respect to x", g_x)
show("max |backprop - finite differences| over W1", np.abs(fd_grad(lambda M: net_loss(x, M, W2), W1) - g_W1).max())

# 6c. A batched linear layer Z = X W^T + b: grad_X = G W, grad_W = G^T X (sum of outer products), grad_b = sum of G.
rng = np.random.default_rng(0)
X, W, bb, R = rng.normal(size=(5, 3)), rng.normal(size=(4, 3)), rng.normal(size=4), rng.normal(size=(5, 4))
batch_loss = lambda X, W, bb: (R * (X @ W.T + bb)).sum()       # any loss whose gradient wrt Z is R
G = R
assert np.allclose(fd_grad(lambda M: batch_loss(M, W, bb), X), G @ W, atol=1e-6)
assert np.allclose(fd_grad(lambda M: batch_loss(X, M, bb), W), G.T @ X, atol=1e-6)
assert np.allclose(G.T @ X, sum(np.outer(G[i], X[i]) for i in range(5)))
assert np.allclose(fd_grad(lambda v: batch_loss(X, W, v), bb), G.sum(0), atol=1e-6)

# 6d. Multiplication counts for a chain of D square layers of width n (scalar loss at the end).
D, n = 10, 1000
show("right to left, matrix x matrix (forward accumulation)", f"{(D - 1) * n ** 3 + n ** 2:.1e}")
show("left to right, vector x matrix (reverse, backprop)", f"{D * n ** 2:.1e}")

print("all checks passed")
