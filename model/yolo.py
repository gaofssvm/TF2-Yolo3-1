import numpy as np
from layers import YoloOutputLayer, YoloOutputBoxLayer, NMSLayer
from model.darknet import darknet_body, darknetconv2d_bn_leaky, darknetconv2d
from tensorflow.python.keras import layers, Model, Input


yolo_anchors = np.array([(10, 13), (16, 30), (33, 23),
                         (30, 61), (62, 45), (59, 119),
                         (116, 90), (156, 198), (373, 326)])


def make_last_layers(x, num_filters, num_anchors, num_classes):
    '''6 Conv2D_BN_Leaky layers followed by a Conv2D_linear layer'''
    out_filters = num_anchors * (num_classes + 5)
    x = darknetconv2d_bn_leaky(x, num_filters, (1, 1))
    x = darknetconv2d_bn_leaky(x, num_filters * 2, (3, 3))
    x = darknetconv2d_bn_leaky(x, num_filters, (1, 1))
    x = darknetconv2d_bn_leaky(x, num_filters * 2, (3, 3))
    x = darknetconv2d_bn_leaky(x, num_filters, (1, 1))
    y = darknetconv2d_bn_leaky(x, num_filters*2, (3, 3))
    y = darknetconv2d(y, out_filters, (1, 1))
    y = YoloOutputLayer(num_anchors, num_classes)(y)
    return x, y


def tiny_yolo_body(inputs, num_anchors, num_classes):
    x1 = darknetconv2d_bn_leaky(inputs, 16, (3, 3))
    x1 = layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x1)
    x1 = darknetconv2d_bn_leaky(x1, 32, (3, 3))
    x1 = layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x1)
    x1 = darknetconv2d_bn_leaky(x1, 64, (3, 3))
    x1 = layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x1)
    x1 = darknetconv2d_bn_leaky(x1, 128, (3, 3))
    x1 = layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x1)
    x1 = darknetconv2d_bn_leaky(x1, 256, (3, 3))

    x2 = layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x1)
    x2 = darknetconv2d_bn_leaky(x2, 512, (3, 3))
    x2 = layers.MaxPooling2D(pool_size=(2, 2), strides=(1, 1), padding='same')(x2)
    x2 = darknetconv2d_bn_leaky(x2, 1024, (3, 3))
    x2 = darknetconv2d_bn_leaky(x2, 256, (1, 1))

    y1 = darknetconv2d_bn_leaky(x2, 512, (3,3))
    y1 = darknetconv2d_bn_leaky(y1, num_anchors*(num_classes+5), (1,1))

    x2 = darknetconv2d_bn_leaky(x2, 128, (1, 1))
    x2 = layers.UpSampling2D(2)(x2)

    y2 = layers.Concatenate()([x2, x1])
    y2 = darknetconv2d_bn_leaky(y2, 256, (3, 3)),
    y2 = darknetconv2d(y2, num_anchors * (num_classes + 5), (1, 1))
    return Model(inputs, [y1, y2])


def yolo_body(inputs, anchors=yolo_anchors, num_classes=80, training=False):
    """Create YOLO_V3 model CNN body in Keras."""
    num_anchors = len(anchors) // 3

    darknet = Model(inputs, darknet_body(inputs))
    x, y1 = make_last_layers(darknet.output, 512, num_anchors, num_classes)

    x = darknetconv2d_bn_leaky(x, 256, (1, 1))
    x = layers.UpSampling2D(2)(x)
    x = layers.Concatenate()([x, darknet.layers[152].output])
    x, y2 = make_last_layers(x, 256, num_anchors, num_classes)

    x = darknetconv2d_bn_leaky(x, 128, (1, 1))
    x = layers.UpSampling2D(2)(x)
    x = layers.Concatenate()([x, darknet.layers[92].output])
    x, y3 = make_last_layers(x, 128, num_anchors, num_classes)
    if training:
        return Model(inputs, (y1, y2, y3), name='Yolo-V3')

    y1 = YoloOutputBoxLayer(anchors[6:], num_classes)(y1)
    y2 = YoloOutputBoxLayer(anchors[3:6], num_classes)(y2)
    y3 = YoloOutputBoxLayer(anchors[0:3], num_classes)(y3)
    outputs = NMSLayer(num_classes)([y1, y2, y3])
    return Model(inputs, outputs, name='Yolo-V3')


if __name__ == "__main__":
    from tensorflow.python.keras.callbacks import TensorBoard
    import os
    os.environ['CUDA_VISIBLE_DEVICES'] = '1'
    inputs_ = Input((416, 416, 3))
    model = yolo_body(inputs_)
    model.summary(line_length=250)
    model_tb = TensorBoard('../logs')
    model_tb.set_model(model)

    x = np.random.random([1, 416, 416, 3])
    output = model.predict(x)
    print()