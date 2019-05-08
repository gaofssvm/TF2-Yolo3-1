import tensorflow as tf


class YoloOutputLayer(tf.keras.layers.Layer):
    def __init__(self, num_anchors, num_classes, **kwargs):
        super(YoloOutputLayer, self).__init__(**kwargs)
        self.num_anchors = num_anchors
        self.num_classes = num_classes

    def build(self, input_shape):
        self.input_h, self.input_w = input_shape[1:3]

    def call(self, x, **kwargs):
        x = tf.reshape(x, (-1, self.input_h, self.input_w, self.num_anchors, self.num_classes + 5))
        return x
