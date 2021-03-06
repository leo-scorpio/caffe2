from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from caffe2.python import core
from hypothesis import given
import caffe2.python.hypothesis_test_util as hu
import hypothesis.strategies as st
import numpy as np


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def sigmoid_cross_entropy_with_logits(x, z):
    return np.maximum(x, 0) - x * z + np.log(1 + np.exp(-np.abs(x)))


def sigmoid_cross_entropy_with_logits_grad(x, z):
    return z - sigmoid(x)


class TestCrossEntropyOps(hu.HypothesisTestCase):
    @given(
        inputs=st.lists(
            elements=st.integers(min_value=1, max_value=5),
            min_size=1,
            max_size=2,
            average_size=2,
        ).flatmap(
            lambda shape: st.tuples(
                hu.arrays(
                    dims=shape,
                    elements=st.one_of(
                        st.floats(min_value=-1.0, max_value=-0.1),
                        st.floats(min_value=0.1, max_value=1.0),
                    )),
                hu.arrays(
                    dims=shape,
                    elements=st.sampled_from([0.0, 1.0]),
                ),
            )
        ),
    )
    def test_sigmoid_cross_entropy_with_logits(self, inputs):
        logits, targets = inputs

        def sigmoid_xentr_logit_ref(logits, targets):
            s = sigmoid_cross_entropy_with_logits(logits, targets)
            m = np.mean(s, axis=len(logits.shape) - 1)
            return (m, )

        def sigmoid_xentr_logit_grad_ref(g_out, outputs, fwd_inputs):
            fwd_logits, fwd_targets = fwd_inputs
            inner_size = fwd_logits.shape[-1]
            m = fwd_targets - sigmoid(fwd_logits)
            g_in = -np.expand_dims(g_out, axis=-1) * m / inner_size
            return (g_in, None)

        op = core.CreateOperator(
            'SigmoidCrossEntropyWithLogits',
            ['logits', 'targets'],
            ['xentropy'])
        self.assertReferenceChecks(
            hu.cpu_do,
            op,
            [logits, targets],
            sigmoid_xentr_logit_ref,
            output_to_grad='xentropy',
            grad_reference=sigmoid_xentr_logit_grad_ref)

    @given(n=st.integers(2, 10),
           **hu.gcs_cpu_only)
    def test_soft_label_cross_entropy(self, n, gc, dc):
        # Initialize X and add 1e-2 for numerical stability
        X = np.random.rand(n).astype(np.float32)
        X = X + 1e-2
        X = np.expand_dims((X / np.sum(X)), axis=0)

        # Initialize label
        label = np.random.rand(n).astype(np.float32)
        label = np.expand_dims((label / np.sum(label)), axis=0)

        # Reference implementation of cross entropy with soft labels
        def soft_label_xentr_ref(X, label):
            xent = [np.sum((-label[0][i] * np.log(max(X[0][i], 1e-20))
                    for i in range(len(X[0]))))]
            return (xent,)

        op = core.CreateOperator("CrossEntropy", ["X", "label"], ["Y"])

        # TODO(surya) Once CrossEntropyOp is ported to GPU, add the respective
        # tests to this unit test.
        self.assertReferenceChecks(
            device_option=gc,
            op=op,
            inputs=[X, label],
            reference=soft_label_xentr_ref,
        )

        self.assertGradientChecks(
            gc, op, [X, label], 0, [0], stepsize=1e-4, threshold=1e-2)

if __name__ == "__main__":
    import unittest
    unittest.main()
