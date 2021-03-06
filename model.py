import tensorflow as tf
from tensorflow.contrib.tensorboard.plugins import projector
from tensorflow.python.framework import ops
from tensorflow.python.ops import gen_nn_ops
import math
import os

@ops.RegisterGradient("MaxPoolWithArgmax")
def _MaxPoolGradWithArgmax(op, grad, unused_argmax_grad):
  return gen_nn_ops._max_pool_grad_with_argmax(op.inputs[0],
                                               grad,
                                               op.outputs[1],
                                               op.get_attr("ksize"),
                                               op.get_attr("strides"),
                                               padding=op.get_attr("padding"))

def weight_variable(shape, name=None, initializer=None):
    if not initializer:
        initial = tf.truncated_normal(shape, stddev=0.1)
    else:
        stddev = math.sqrt(2. / (kl**2 * dl))
        initial = tf.truncated_normal_initializer(stddev=stddev)

        initial = tf.truncated_normal_initializer(shape, stddev=0.1)

    return tf.Variable(initial, name=name)

def weight_variavle_with_weight_decay(name, shape, initializer, wd):

    var = tf.get_variable(name, shape, initializer=initializer)

    if wd is not None:
        with tf.variable_scope("weigth_decay"):
            weight_decay = tf.multiply(tf.nn.l2_loss(var), wd, name='weight_loss')
        tf.add_to_collection('losses', weight_decay)
        with tf.device("/cpu:0"):
            tf.summary.scalar('weight_decay/' + name, weight_decay)

    return var

def msra_initializer(kl, dl):
    """
    kl for kernel size, dl for filter number
    """
    stddev = math.sqrt(2. / (kl**2 * dl))
    return tf.truncated_normal_initializer(stddev=stddev)

def bias_variable(shape, name=None):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial, name=name)

def conv2d(x, W):
    return tf.nn.conv2d(x, W, strides=[1, 1, 1, 1], padding='SAME')

def batch_norm(x):
    return tf.contrib.layers.batch_norm(x, is_training=True, center=False, updates_collections=None, fused=True)

def max_pool_2x2(x):
    return tf.nn.max_pool_with_argmax(x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')

def variable_summaries(name, var):
    with tf.device("/cpu:0"):
        with tf.variable_scope('summaries'):
            mean = tf.reduce_mean(var)
            tf.summary.scalar('mean/' + name, mean)
            with tf.variable_scope('stddev'):
                stddev = tf.sqrt(tf.reduce_mean(tf.square(var - mean)))
            tf.summary.scalar('stddev/' + name, stddev)
            tf.summary.scalar('max/' + name, tf.reduce_max(var))
            tf.summary.scalar('min/' + name, tf.reduce_min(var))
            tf.summary.histogram(name, var)

def unravel_argmax(argmax, shape):
    output_list = []
    with tf.device("/cpu:0"):
        output_list.append(argmax // (shape[2] * shape[3]))
        output_list.append(argmax % (shape[2] * shape[3]) // shape[3])
        return tf.pack(output_list)

#def unpool_layer2x2(x, raveled_argmax, out_shape):
#    argmax = unravel_argmax(raveled_argmax, tf.to_int64(out_shape))
#    output = tf.zeros([out_shape[1], out_shape[2], out_shape[3]])
#
#    height = tf.shape(output)[0]
#    width = tf.shape(output)[1]
#    channels = tf.shape(output)[2]
#
#    t1 = tf.to_int64(tf.range(channels))
#    t1 = tf.tile(t1, [((width + 1) // 2) * ((height + 1) // 2)])
#    t1 = tf.reshape(t1, [-1, channels])
#    t1 = tf.transpose(t1, perm=[1, 0])
#    t1 = tf.reshape(t1, [channels, (height + 1) // 2, (width + 1) // 2, 1])
#
#    t2 = tf.squeeze(argmax)
#    t2 = tf.pack((t2[0], t2[1]), axis=0)
#    t2 = tf.transpose(t2, perm=[3, 1, 2, 0])
#
#    t = tf.concat(3, [t2, t1])
#    indices = tf.reshape(t, [((height + 1) // 2) * ((width + 1) // 2) * channels, 3])
#
#    x1 = tf.squeeze(x)
#    x1 = tf.reshape(x1, [-1, channels])
#    x1 = tf.transpose(x1, perm=[1, 0])
#    values = tf.reshape(x1, [-1])
#
#    delta = tf.SparseTensor(indices, values, tf.to_int64(tf.shape(output)))
#
#    #return tf.expand_dims(tf.sparse_tensor_to_dense(tf.sparse_reorder(delta)), 0)
#
#def unpool_layer2x2_batch(x, argmax, out_shape):
#    '''
#    Args:
#	x: 4D tensor of shape [batch_size x height x width x channels]
#	argmax: A Tensor of type Targmax. 4-D. The flattened indices of the max
#	values chosen for each output.
#    Return:
#	4D output tensor of shape [batch_size x 2*height x 2*width x channels]
#    '''
#    with tf.variable_scope("unpool_layer2x2"):
#        with tf.device("/cpu:0"):
#            #x_shape = tf.shape(x)
#            #out_shape = [x_shape[0], x_shape[1]*2, x_shape[2]*2, x_shape[3]]
#
#            batch_size = out_shape[0]
#            height = out_shape[1]
#            width = out_shape[2]
#            channels = out_shape[3]
#
#            argmax_shape = tf.to_int64([batch_size, height, width, channels])
#            argmax = unravel_argmax(argmax, argmax_shape)
#
#            t1 = tf.to_int64(tf.range(channels))
#            t1 = tf.tile(t1, [batch_size*(width//2)*(height//2)])
#            t1 = tf.reshape(t1, [-1, channels])
#            t1 = tf.transpose(t1, perm=[1, 0])
#            t1 = tf.reshape(t1, [channels, batch_size, height//2, width//2, 1])
#            t1 = tf.transpose(t1, perm=[1, 0, 2, 3, 4])
#
#            t2 = tf.to_int64(tf.range(batch_size))
#            t2 = tf.tile(t2, [channels*(width//2)*(height//2)])
#            t2 = tf.reshape(t2, [-1, batch_size])
#            t2 = tf.transpose(t2, perm=[1, 0])
#            t2 = tf.reshape(t2, [batch_size, channels, height//2, width//2, 1])
#
#            t3 = tf.transpose(argmax, perm=[1, 4, 2, 3, 0])
#
#            t = tf.concat(4, [t2, t3, t1])
#            indices = tf.reshape(t, [(height//2)*(width//2)*channels*batch_size, 4])
#
#            x1 = tf.transpose(x, perm=[0, 3, 1, 2])
#            values = tf.reshape(x1, [-1])
#
#            delta = tf.SparseTensor(indices, values, tf.to_int64(out_shape))
#            return tf.reshape(tf.sparse_tensor_to_dense(tf.sparse_reorder(delta)), out_shape)


def unpool_layer2x2_batch(updates, mask, ksize=[1, 2, 2, 1]):
    with tf.device("/cpu:0"):
	input_shape = updates.get_shape().as_list()
	#  calculation new shape
	output_shape = (input_shape[0], input_shape[1] * ksize[1], input_shape[2] * ksize[2], input_shape[3])
	# calculation indices for batch, height, width and feature maps
	one_like_mask = tf.ones_like(mask)
	batch_range = tf.reshape(tf.range(output_shape[0], dtype=tf.int64), shape=[input_shape[0], 1, 1, 1])
	b = one_like_mask * batch_range
	y = mask // (output_shape[2] * output_shape[3])
	x = mask % (output_shape[2] * output_shape[3]) // output_shape[3]
	feature_range = tf.range(output_shape[3], dtype=tf.int64)
	f = one_like_mask * feature_range
	# transpose indices & reshape update values to one dimension
	updates_size = tf.size(updates)
	indices = tf.transpose(tf.reshape(tf.stack([b, y, x, f]), [4, updates_size]))
	values = tf.reshape(updates, [updates_size])
	ret = tf.scatter_nd(indices, values, output_shape)
	return ret

class ImageClassifier:

    def __init__(self, num_classes, image_size, batch_size=50, num_epochs=500, dropout_rate=0.5, eval=False, checkpoint_file="output/model.ckpt-1000-5000-2500"):
        self.image_size = image_size
        self.num_classes = num_classes
        self.batch_size = batch_size
        self.num_epochs = num_epochs
        self.dropout_rate = dropout_rate
        self.checkpoint_file = checkpoint_file
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
            if not eval:
                self.loss(
                    self.inference(self.x),
                    self.y
                )
            else:
                self.evaluate(self.x, self.y)

        with tf.device("/cpu:0"):
            self.saver = tf.train.Saver()
            self.run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
            self.run_metadata = tf.RunMetadata()

        self.merged = tf.summary.merge_all()


    def inference(self, x):


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

    def loss(self, logits, labels):
        labels = tf.reshape(labels, [self.batch_size, self.image_size * self.image_size])

        logits, labels, loss = self.calculate_loss(logits, labels)
        self.optimize_loss(loss)

        with tf.name_scope("output"):
            prediction = self.predict(logits, labels)
            self.calculate_accuracy(prediction)


    def evaluate(self, images, labels):

        # build a graph that computes predictions from the inference model
        logits = self.inference(images)
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
            b_conv = bias_variable([64])
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
            W_conv = weight_variable([3, 3, 64, 64])
            variable_summaries("W-conv-decode%s" % layer_no, W_conv)
            b_conv = bias_variable([64])
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
                W_conv_class = weight_variavle_with_weight_decay(
                    "W_conv_class",
                    [1, 1, 64, self.num_classes],
                    msra_initializer(1, 64),
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


    def calculate_loss(self, logits, labels):
        with tf.variable_scope('Loss') as scope_conv:

            logits = tf.reshape(logits, [-1, self.num_classes])
            labels = tf.reshape(labels, [-1])

            cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(
                    logits=logits, labels=labels)
            cross_entropy_mean = tf.reduce_mean(cross_entropy)
            with tf.device("/cpu:0"):
                tf.summary.scalar('loss', cross_entropy_mean)
            self.calculated_loss = cross_entropy_mean
            tf.add_to_collection('losses', cross_entropy_mean)

            loss = tf.add_n(tf.get_collection('losses'), name="total_loss")

            #logits = tf.reshape(logits, [-1, 255])
            #epsilon = tf.constant(value=1e-10)
            #logits  = logits + epsilon

            #labels_flat = tf.reshape(labels, (-1, 1))

            #labels = tf.reshape(tf.one_hot(labels_flat, depth=255), [-1, 255])

            #softmax = tf.nn.softmax(logits)

            #cross_entropy = - tf.reduce_sum((labels * tf.log(softmax + epsilon)), reduction_indices=[1])

            #cross_entropy_mean = tf.reduce_mean(cross_entropy)
            #self.calculated_loss = cross_entropy_mean

            #tf.add_to_collection('losses', cross_entropy_mean)

            #loss = tf.add_n(tf.get_collection('losses'))
            #tf.scalar_summary('loss', loss)
        return logits, labels, loss

        #    cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(y_conv, y)
        #    loss = tf.reduce_mean(cross_entropy)
        #    tf.scalar_summary('loss', loss)
        #return cross_entropy

    def optimize_loss(self, cross_entropy):
        with tf.variable_scope('Optimization') as scope_conv:
            self.train_step = tf.train.AdamOptimizer(1e-4)
            gradients_and_vars = self.train_step.compute_gradients(cross_entropy, var_list=tf.get_collection('loss_vars'))
            self.train_step = self.train_step.apply_gradients(gradients_and_vars)


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
        self.saver.restore(sess, self.checkpoint_file)




