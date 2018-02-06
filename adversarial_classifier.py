import tensorflow as tf
from tensorflow.contrib.tensorboard.plugins import projector
from tensorflow.python.framework import ops
from tensorflow.python.ops import gen_nn_ops
import math
import os

from utils import *

class ImageClassifier:

    def __init__(self, num_classes, image_size, batch_size=50, num_epochs=500, dropout_rate=0.5, eval=False, checkpoint_file="output/model.ckpt-1000-5000-2500"):
        self.image_size = image_size
        self.num_classes = num_classes
        self.batch_size = batch_size
        self.num_epochs = num_epochs
        self.dropout_rate = dropout_rate
        self.checkpoint_file = checkpoint_file
        print(self.checkpoint_file)
        self.eval = eval
        self.optimize_vars = []
        self.argmax = {}

        with tf.device("/cpu:0"):
            with tf.variable_scope("inputs"):
                self.x = tf.placeholder(tf.float32, [self.batch_size, image_size, image_size, 4], name="inputs")
                self.y = tf.placeholder(tf.int64, [self.batch_size, image_size, image_size], name="labels")
                self.keep_prob = tf.placeholder(tf.float32, name="dropout_keep_prob")


            # input and label summaries
            self.image_image = tf.slice(self.x, [0, 0, 0, 0], [-1, self.image_size, self.image_size, 3])
            tf.summary.image('input',
                    # slice removes nir layer which is stored as alpha
                    self.image_image,
                    max_outputs=50)
            self.label_image = scaled_label = tf.cast(self.y, tf.float32) #((tf.cast(self.y, tf.float32)/self.num_classes)*255)
            tf.summary.image('label',
                    tf.reshape(scaled_label, [-1, self.image_size, self.image_size, 1]),
                    max_outputs=50)

        with tf.device("/gpu:0"):

            segment = self.segmentation(self.x)

            if not eval:

                adv_seg = self.adversarial(segment, self.x, "seg", summary=True)

                y_one_hot = tf.one_hot(self.y, self.num_classes)
                adv_labels = self.adversarial(y_one_hot, self.x, "lbl", reuse=True)

                self.loss( segment, adv_seg, adv_labels, self.y )
            else:
                self.evaluate(segment, self.y)

        with tf.device("/cpu:0"):
            self.saver = tf.train.Saver()
            self.run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
            self.run_metadata = tf.RunMetadata()

        self.merged = tf.summary.merge_all()


    def segmentation(self, x):


	with tf.device("/cpu:0"):
	    lrn = self.local_response_normalization_layer(x)

	    image = tf.slice(lrn, [0, 0, 0, 0], [-1, self.image_size, self.image_size, 3])
	    tf.summary.image('lrn_input',
		    # slice removes nir layer which is stored as alpha
		    image,
		    max_outputs=50)

        num_layers = 5

        with tf.device("/gpu:0"):


            lrn = tf.reshape(lrn, [self.batch_size, self.image_size, self.image_size, 4])

            previous_layer = lrn
            for layer in range(num_layers):
                print("Generating Convolutional Layer %s" % layer)
                with tf.variable_scope("encoder_%s" % layer):
                    num_channels = 64 if layer != 0 else 4
                    previous_layer = self.conv_layer(layer, num_channels, previous_layer)


            for layer in reversed(range(num_layers)):
                with tf.variable_scope("decoder_%s" % layer):
                    print("Generating Deconvolutional Layer %s" % layer)
                    deconv = self.deconv_layer(layer, previous_layer)
                    previous_layer = self.conv_decode_layer(layer, deconv)

            conv_class = self.conv_class_layer(previous_layer)

        return conv_class


    def adversarial(self, y, x, layer_name, summary=False, reuse=None):
        with tf.variable_scope("adversarial", reuse=reuse):

            with tf.variable_scope('x_conv_0'):
                x = tf.cast(x, tf.float32)
                W_conv = weight_variable([3, 3, 4, 64], "W_x_conv_0")
                if summary: variable_summaries("W_x_conv_0", W_conv)
                b_conv = bias_variable([64], "b_x_conv_0")
                if summary: variable_summaries("b_x_conv_0", b_conv)

                tf.add_to_collection("loss_vars", W_conv)
                tf.add_to_collection("loss_vars", b_conv)

                conv = conv2d(x, W_conv) + b_conv
                bn = batch_norm(conv)
                x = tf.nn.relu(bn)

                if summary: self.image_summary('x_conv_0/filters', x)

            with tf.variable_scope('y_conv_0'):
                y = tf.cast(y, tf.float32)
                W_conv = weight_variable([3, 3, self.num_classes, 64], "W_y_conv_0")
                if summary: variable_summaries("W_y_conv_0", W_conv)
                b_conv = bias_variable([64], "b_y_conv_0")
                if summary: variable_summaries("b_y_conv_0", b_conv)

                tf.add_to_collection("loss_vars", W_conv)
                tf.add_to_collection("loss_vars", b_conv)

                conv = conv2d(y, W_conv) + b_conv
                bn = batch_norm(conv)
                y = tf.nn.relu(bn)

                if summary: self.image_summary('y_conv_0/filters', y)

            with tf.variable_scope("xy_concat"):

                concat = tf.concat([x, y], 3)

            with tf.variable_scope("xy_conv_0"):

                W_conv = weight_variable([3, 3, 128, 128], "W_xy_conv_0")
                if summary: variable_summaries("W_xy_conv_0", W_conv)
                b_conv = bias_variable([128], "b_xy_conv_0")
                if summary: variable_summaries("b_xy_conv_0", b_conv)

                tf.add_to_collection("loss_vars", W_conv)
                tf.add_to_collection("loss_vars", b_conv)

                conv = conv2d(concat, W_conv) + b_conv
                bn = batch_norm(conv)
                xy_0 = tf.nn.relu(bn)

                if summary: self.image_summary('xy_conv_0/filters', xy_0)


            with tf.variable_scope("xy_conv_1"):

                W_conv = weight_variable([3, 3, 128, 256], "W_xy_conv_1")
                if summary: variable_summaries("W_xy_conv_1", W_conv)
                b_conv = bias_variable([256], "b_xy_conv_1")
                if summary: variable_summaries("b_xy_conv_1", b_conv)

                tf.add_to_collection("loss_vars", W_conv)
                tf.add_to_collection("loss_vars", b_conv)

                conv = conv2d(xy_0, W_conv) + b_conv
                bn = batch_norm(conv)
                xy_1 = tf.nn.relu(bn)

                if summary: self.image_summary('xy_conv_1/filters', xy_1)

            with tf.variable_scope("xy_conv_2"):

                W_conv = weight_variable([3, 3, 256, 512], "W_xy_conv_2")
                if summary: variable_summaries("W_xy_conv_2", W_conv)
                b_conv = bias_variable([512], "b_xy_conv_2")
                if summary: variable_summaries("b_xy_conv_2", b_conv)

                tf.add_to_collection("loss_vars", W_conv)
                tf.add_to_collection("loss_vars", b_conv)

                conv = conv2d(xy_1, W_conv) + b_conv
                bn= batch_norm(conv)
                xy_2 = tf.nn.relu(bn)

                if summary: self.image_summary('xy_conv_2/filters', xy_2)

            with tf.variable_scope("xy_conv_3"):

                W_conv = weight_variable([3, 3, 512, 2], "W_xy_conv_3")
                if summary: variable_summaries("W_xy_conv_3", W_conv)
                b_conv = bias_variable([2], "b_xy_conv_3")
                if summary: variable_summaries("b_xy_conv_3", b_conv)

                tf.add_to_collection("loss_vars", W_conv)
                tf.add_to_collection("loss_vars", b_conv)

                conv = conv2d(xy_2, W_conv) + b_conv
                bn = batch_norm(conv)
                xy_3 = tf.nn.relu(bn)

                if summary: self.image_summary('xy_conv_3/filters', xy_3)

            with tf.variable_scope("xy_softmax"):
                xy_softmax = tf.nn.softmax(xy_3)
                if summary: self.image_summary('xy_softmax/filters', xy_softmax)

            return xy_softmax


    def loss(self, seg_logits, seg_adv, seg_lbl, labels):
        labels = tf.reshape(labels, [self.batch_size, self.image_size * self.image_size])

        logits, labels = self.calculate_loss(seg_logits, seg_adv, seg_lbl, labels)

        with tf.variable_scope('Optimization') as scope_conv:
            self.train_step = tf.train.AdamOptimizer(1e-4)
            gradients_and_vars = self.train_step.compute_gradients(tf.losses.get_total_loss(), var_list=tf.get_collection("loss_vars"))
            self.train_step = self.train_step.apply_gradients(gradients_and_vars)

        with tf.name_scope("output"):
            prediction = self.predict(logits, labels)
            self.calculate_accuracy(prediction)


    def evaluate(self, logits, labels):

        self.image_tensor = logits

        img = tf.argmax(logits, 3)
        img = tf.cast(img, tf.float32)
        self.class_image = tf.reshape(img, [-1, self.image_size, self.image_size, 1])
        with tf.device("/cpu:0"):
            tf.summary.image("classification-map", self.class_image, max_outputs=500)

        labels = tf.cast(labels, tf.int32)
        #labels = tf.argmax(labels, 1)

        logits = tf.reshape(logits, [-1, self.num_classes])
        labels = tf.reshape(labels, [-1])

        # calculate predictions
        with tf.device("/cpu:0"):
            self.top_k_op = tf.nn.in_top_k(logits, labels, 1)


    def local_response_normalization_layer(self, x):
        return tf.nn.local_response_normalization(x)



    def conv_layer(self, layer_no, input_channels, x):

        with tf.variable_scope('conv%s' % layer_no) as scope_conv:
            W_conv = weight_variable([3, 3, input_channels, 64], "W_conv%s" % layer_no)
            variable_summaries("W-conv%s" % layer_no, W_conv)
            b_conv = bias_variable([64], "b_conv%s" % layer_no)
            variable_summaries("b-conv%s" % layer_no, b_conv)

            tf.add_to_collection("loss_vars", W_conv)
            tf.add_to_collection("loss_vars", b_conv)

            h_conv = conv2d(x, W_conv) + b_conv
            h_batch_norm = batch_norm(h_conv)
            h_relu = tf.nn.relu(h_batch_norm)
            h_pool, self.argmax[layer_no]  = max_pool_2x2(h_relu)

            self.image_summary('conv1/filters', h_relu)

            return h_pool


    def deconv_layer(self, layer_no,  h_pool):
        with tf.variable_scope('deconv%s' % layer_no) as scope_conv:
            h_deconv = unpool_layer2x2_batch(h_pool, self.argmax[layer_no])
            self.image_summary('deconv%s/filters' % layer_no, h_deconv)

            return h_deconv


    def conv_decode_layer(self, layer_no, h_deconv):
        with tf.variable_scope('conv_decode%s' % layer_no) as scope_conv:
            W_conv = weight_variable([3, 3, 64, 64], "W_conv_decode_%s" % layer_no)
            variable_summaries("W-conv-decode%s" % layer_no, W_conv)
            b_conv = bias_variable([64], "b_conv_decode_%s" % layer_no)
            variable_summaries("b-conv-decode%s" % layer_no, b_conv)

            tf.add_to_collection("loss_vars", W_conv)
            tf.add_to_collection("loss_vars", b_conv)

            h_conv = tf.nn.conv2d(h_deconv, W_conv, [1, 1, 1, 1], padding="SAME") + b_conv
            h_batch_norm = batch_norm(h_conv)
            h_relu = tf.nn.relu(h_batch_norm)
            h_dropout = tf.nn.dropout(h_relu, self.keep_prob)
            self.image_summary('conv-decode%s/filters' % layer_no, h_relu)

            return h_dropout


    def deconv3_layer(self, h_pool2):
        with tf.variable_scope('deconv3') as scope_conv:
            #W_deconv = weight_variable([2, 2, 64, 64])
            #variable_summaries("W-deconv3", W_deconv)

            h_deconv = unpool_layer2x2_batch(h_pool2, self.argmax3)
            h_deconv = tf.reshape(h_deconv, [self.batch_size, self.image_size/4, self.image_size/4, 64])

            self.image_summary('deconv3/filters', h_deconv)

            return h_deconv

    def conv_decode3_layer(self, h_deconv1):
        with tf.variable_scope('conv_decode3') as scope_conv:
            W_conv = weight_variable([3, 3, 64, 64])
            variable_summaries("W-conv-decode3", W_conv)
            b_conv = bias_variable([64])
            variable_summaries("b-conv-decode3", b_conv)

            tf.add_to_collection("loss_vars", W_conv)
            tf.add_to_collection("loss_vars", b_conv)

            h_conv = tf.nn.conv2d(h_deconv1, W_conv, [1, 1, 1, 1], padding="SAME") + b_conv
            h_batch_norm = batch_norm(h_conv)
            h_relu = tf.nn.relu(h_batch_norm)
            h_dropout = tf.nn.dropout(h_relu, self.keep_prob)
            self.image_summary('conv-decode3/filters', h_relu)

            return h_dropout

    def deconv2_layer(self, h_pool2):
        with tf.variable_scope('deconv2') as scope_conv:
            #W_deconv = weight_variable([2, 2, 64, 64])
            #variable_summaries("W-deconv2", W_deconv)

            h_deconv = unpool_layer2x2_batch(h_pool2, self.argmax2)
            h_deconv = tf.reshape(h_deconv, [self.batch_size, self.image_size/2, self.image_size/2, 64])

            self.image_summary('deconv2/filters', h_deconv)

            return h_deconv

    def conv_decode2_layer(self, h_deconv1):
        with tf.variable_scope('conv_decode2') as scope_conv:
            W_conv = weight_variable([7, 7, 64, 64])
            variable_summaries("W-conv-decode2", W_conv)
            b_conv = bias_variable([64])
            variable_summaries("b-conv-decode2", b_conv)

            tf.add_to_collection("loss_vars", W_conv)
            tf.add_to_collection("loss_vars", b_conv)

            h_conv = tf.nn.conv2d(h_deconv1, W_conv, [1, 1, 1, 1], padding="SAME") + b_conv
            h_batch_norm = batch_norm(h_conv)
            h_relu = tf.nn.relu(h_batch_norm)
            #h_dropout = tf.nn.dropout(h_relu, self.keep_prob)
            self.image_summary('filters', h_relu)

            #return h_dropout
            return h_relu


    def deconv1_layer(self, h_pool2):
        with tf.variable_scope('deconv1') as scope_conv:
            #W_deconv1 = weight_variable([2, 2, 64, 64])
            #variable_summaries("W-deconv1", W_deconv1)

            h_deconv = unpool_layer2x2_batch(h_pool2, self.argmax1)
            h_deconv = tf.reshape(h_deconv, [self.batch_size, self.image_size, self.image_size, 64])
            self.image_summary('deconv1/filters', h_deconv)

            return h_deconv


    def conv_decode1_layer(self, h_deconv2):
        with tf.variable_scope('conv-decode1') as scope_conv:
            with tf.variable_scope("variables"):
                W_conv = weight_variable([7, 7, 64, 64])
                variable_summaries("W-conv-decode1", W_conv)
                b_conv = bias_variable([64])
                variable_summaries("b-conv-decode1", b_conv)

            tf.add_to_collection("loss_vars", W_conv)
            tf.add_to_collection("loss_vars", b_conv)

            h_conv = tf.nn.conv2d(h_deconv2, W_conv, [1, 1, 1, 1], padding="SAME") + b_conv
            h_batch_norm = batch_norm(h_conv)
            h_relu = tf.nn.relu(h_batch_norm)
            self.image_summary('conv-decode1/filters', h_relu)

            return h_relu

    def conv_class_layer(self, h_conv_decode1):
        with tf.variable_scope('conv-classification') as scope_conv:

            with tf.variable_scope("variables"):
                W_conv_class = weight_variable_with_weight_decay(
                    "W_conv_class",
                    msra_initializer([1, 1, 64, self.num_classes], 1, 64),
                    0.0005)
                variable_summaries("W-conv-classification", W_conv_class)
                b_conv_class = bias_variable([self.num_classes], name="b_conv_class")
                variable_summaries("b-conv-classification", b_conv_class, )

            tf.add_to_collection("loss_vars", W_conv_class)
            tf.add_to_collection("loss_vars", b_conv_class)

            with tf.variable_scope("conv"):
                self.emb = tf.nn.conv2d(h_conv_decode1, W_conv_class, [1, 1, 1, 1], padding="SAME")
                self.emb = tf.add(self.emb, b_conv_class, name="add_bias")
                self.image_summary('conv_class_layer/filters', self.emb )

            with tf.variable_scope("generate-class-image"):
                # combine conv_class filters into single classification image
                class_image = tf.argmax(tf.reshape(tf.round(self.emb), [-1, self.num_classes, self.image_size, self.image_size]), 1)
                #class_image = tf.reduce_max(max_indices, reduction_indices=[2], keep_dims=True)
                self.class_image = class_image

                class_image = tf.reshape(class_image, [-1, self.image_size, self.image_size, 1])
                class_image = tf.cast(class_image, tf.float32)

                self.image_summary("class-image", class_image)

        return self.emb


    def calculate_loss(self, seg_logits, adv_seg, adv_labels, labels):
        with tf.variable_scope('Loss') as scope_conv:

            logits = tf.reshape(seg_logits, [-1, self.num_classes])
            labels = tf.reshape(labels, [-1])

            # segmentation loss
            cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(
                    logits=logits, labels=labels)
            cross_entropy_mean = tf.reduce_mean(cross_entropy)
            with tf.device("/cpu:0"):
                tf.summary.scalar('segmentation_loss', cross_entropy_mean)
            self.calculated_loss = cross_entropy_mean
            tf.losses.add_loss(cross_entropy_mean)

            # adversarial loss

            def bce(output, target, epsilon=1e-8):
                return tf.reduce_mean(tf.reduce_sum(-(target * tf.log(output + epsilon) + (1. - target) * tf.log(1. - output + epsilon)), axis=1))


            seg_target = tf.ones([self.batch_size, self.image_size, self.image_size])
            seg_target = tf.cast(tf.one_hot(tf.cast(seg_target, tf.int32), 2), tf.float32)
            adv_seg_loss = bce(adv_seg, seg_target)

            with tf.device("/cpu:0"):
                tf.summary.scalar("adversarial_segmentation_loss", adv_seg_loss)

            lbl_target = tf.zeros([self.batch_size, self.image_size, self.image_size])
            lbl_target = tf.cast(tf.one_hot(tf.cast(lbl_target, tf.int32), 2), tf.float32)
            adv_lbl_loss = bce(adv_labels, lbl_target)

            with tf.device("/cpu:0"):
                tf.summary.scalar("adversarial_label_loss", adv_lbl_loss)

            l = -0.5e-1
            shift = 5
            adv_loss = l * ( adv_seg_loss + adv_lbl_loss) + shift
            tf.losses.add_loss(adv_loss)

            with tf.device("/cpu:0"):
                tf.summary.scalar("adversarial_loss", adv_loss)
                tf.summary.scalar("total_loss", tf.losses.get_total_loss())


        return logits, labels



    def predict(self, y_conv, y):
        with tf.variable_scope('Prediction') as scope_conv:
            y = tf.reshape(y, [-1])
            correct_prediction = tf.equal(tf.argmax(y_conv, 1), y)
            with tf.device("/cpu:0"):
                tf.summary.scalar("correct-predictions", tf.reduce_sum(tf.cast(correct_prediction, tf.float32)))

                prediction_image = tf.reshape(tf.cast(correct_prediction, tf.float32), [-1, self.image_size, self.image_size, 1])
                tf.summary.image("prediction-image", prediction_image)

        return correct_prediction

    def calculate_accuracy(self, correct_prediction):
        # TODO: http://stackoverflow.com/questions/37746670/tensorflow-multi-label-accuracy-calculation
        with tf.variable_scope('Accuracy') as scope_conv:
            self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
            with tf.device("/cpu:0"):
                tf.summary.scalar('accuracy', self.accuracy)

    def image_summary(self, tag_name, h_conv):
        with tf.variable_scope("image_summary"):
            with tf.device("/cpu:0"):
                h_conv_features = tf.unstack(h_conv, axis=3)
                h_conv_max = tf.reduce_max(h_conv)
                h_conv_features_padded = map(lambda t: tf.pad(t-h_conv_max, [[0,0], [0,1], [0,0]]) + h_conv_max, h_conv_features)
                h_conv_concated = tf.concat(h_conv_features_padded, 1)
                h_conv_imgs = tf.expand_dims(h_conv_concated, -1)

                tf.summary.image(tag_name, h_conv_imgs, max_outputs=5)



    def train(self, sess, batch, eval=False):
        summary, accuracy, loss, emb, _ = sess.run([self.merged, self.accuracy, self.calculated_loss, self.emb, self.train_step],
                feed_dict={
                self.x: batch[0],
                self.y: batch[1],
                self.keep_prob: self.dropout_rate
            },
            options=self.run_options,
            run_metadata=self.run_metadata)
        return accuracy, loss, summary, self.run_metadata, emb

    def evaluate_once(self, sess,batch):
        predictions, summary, image, label, class_img, img = sess.run([self.top_k_op, self.merged, self.image_image, self.label_image, self.class_image, self.image_tensor],
            feed_dict={
                self.keep_prob: 1,
                self.x: batch[0],
                self.y: batch[1]
        })

        return predictions, summary, image, label, class_img, img

    def save(self, sess, global_step=None):
        return self.saver.save(sess, self.checkpoint_file, global_step=global_step)

    def load(self, sess):

        self.saver.restore(sess, tf.train.latest_checkpoint(self.checkpoint_file))



