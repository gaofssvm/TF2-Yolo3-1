import config
import tensorflow as tf
import tensorflow_datasets as tfds
from losses import YoloLoss
from model import yolov3
from utils import parse_aug_fn, parse_fn, transform_targets, trainable_model
from train import training_model
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

output_layer = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
anchor_masks = config.yolo_anchor_masks


def multi_scale_training_model(model, callbacks, classes=80, step=1):
    if step == 1:
        batch_size = 32
        epoch_step = 10
    else:
        batch_size = 8
        epoch_step = 10

    start_epoch = 0
    for lr in [1e-3, 1e-4]:
        for scale in [320, 352, 384, 416, 448, 480, 512, 544, 576, 608, 416]:
            if scale == 416 and lr == 1e-4:
                print('Last round')
                epoch_step = 50

            anchors = config.yolo_anchors / scale
            grid_size = scale // 32

            # Training dataset setting
            AUTOTUNE = tf.data.experimental.AUTOTUNE  # 自動調整模式
            combined_split = tfds.Split.TRAIN + tfds.Split.VALIDATION
            train_data = tfds.load("voc2007", split=combined_split)    # 取得訓練數據
            train_data = train_data.shuffle(1000)  # 打散資料集
            train_data = train_data.map(lambda dataset: parse_aug_fn(dataset, (scale, scale)), num_parallel_calls=AUTOTUNE)
            train_data = train_data.batch(batch_size)
            train_data = train_data.map(lambda x, y: transform_targets(x, y, anchors, anchor_masks, grid_size),
                                        num_parallel_calls=AUTOTUNE)
            train_data = train_data.prefetch(buffer_size=AUTOTUNE)

            # Validation dataset setting
            val_data = tfds.load("voc2007", split=tfds.Split.TEST)
            val_data = val_data.map(lambda dataset: parse_fn(dataset, (scale, scale)), num_parallel_calls=AUTOTUNE)
            val_data = val_data.batch(batch_size)
            val_data = val_data.map(lambda x, y: transform_targets(x, y, anchors, anchor_masks, grid_size),
                                    num_parallel_calls=AUTOTUNE)
            val_data = val_data.prefetch(buffer_size=AUTOTUNE)

            # Training
            optimizer = tf.keras.optimizers.Adam(lr=lr)
            model.compile(optimizer=optimizer,
                          loss=[YoloLoss(anchors[mask], classes=classes) for mask in anchor_masks],
                          run_eagerly=False)
            model.fit(train_data,
                      epochs=start_epoch + epoch_step,
                      callbacks=callbacks,
                      validation_data=val_data,
                      initial_epoch=start_epoch)
            start_epoch += epoch_step


def main():
    # Dataset Info
    _, info = tfds.load("voc2007", split=tfds.Split.TRAIN, with_info=True)
    classes = info.features['labels'].num_classes

    # Create model
    model = yolov3((None, None, 3), num_classes=classes, training=True)
    model.summary()

    # Load Weights
    model.load_weights(config.yolo_weights, by_name=True)

    # Callbacks function
    log_dir = 'logs-yolo-multi-scale'
    model_dir = log_dir + '/models'
    os.makedirs(model_dir, exist_ok=True)
    model_tb = tf.keras.callbacks.TensorBoard(log_dir=log_dir)
    model_mckp = tf.keras.callbacks.ModelCheckpoint(model_dir + '/best-model-ep{epoch:03d}.h5',
                                                    monitor='val_loss',  # TODO: mAP
                                                    save_best_only=True,
                                                    mode='min')
    model_ep = tf.keras.callbacks.EarlyStopping(patience=15, verbose=1)
    mdoel_rlr = tf.keras.callbacks.ReduceLROnPlateau(verbose=1)

    # Freeze layers
    darknet = model.get_layer('Yolo_DarkNet')
    trainable_model(darknet, trainable=False)

    # 1) Training model step1
    print("Start teraining Step1")
    multi_scale_training_model(model,
                               callbacks=[model_tb, model_mckp, mdoel_rlr],
                               classes=classes,
                               step=1)

    # # Unfreeze layers
    # trainable_model(darknet, trainable=True)
    #
    # # 2) Training model step2
    # print("Start teraining Step2")
    # training_model(model,
    #                callbacks=[model_tb, model_mckp, mdoel_rlr, model_ep],
    #                classes=classes,
    #                step=2)


if __name__ == '__main__':
    main()