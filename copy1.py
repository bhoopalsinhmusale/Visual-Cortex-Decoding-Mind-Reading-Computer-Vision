# -*- coding: utf-8 -*-
"""Coy1.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1uOf04e-1s_Z9bdh4E16f3oif5aQo6_0o

## Setup
"""

!apt install caffe-cuda



# Commented out IPython magic to ensure Python compatibility.
# %cd /content/
!chmod a+x downloaddata.sh

# Commented out IPython magic to ensure Python compatibility.
! ./downloaddata.sh

!chmod a+x /content/DeepImageReconstruction/net/downloadnet.sh

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/DeepImageReconstruction/net/
!ls
!./downloadnet.sh vgg19

"""## Code init
###  ICNN Loss
"""

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/

import numpy as np
import PIL.Image
import scipy.io as sio
import scipy.ndimage as nd
import os
from datetime import datetime
from scipy.optimize import minimize
import pickle
from itertools import product

import caffe




def L2_loss(feat, feat0, mask=1.):
    d = feat - feat0
    loss = (d*d*mask).sum()
    grad = 2 * d * mask
    return loss, grad


def L1_loss(feat, feat0, mask=1.):
    d = feat - feat0
    loss = np.abs(d*mask).sum()
    grad = np.sign(d)*mask
    return loss, grad


def inner_loss(feat, feat0, mask=1.):
    loss = -(feat*feat0*mask).sum()
    grad = -feat0*mask
    return loss, grad


def gram(feat, mask=1.):
    feat = (feat * mask).reshape(feat.shape[0], -1)
    feat_gram = np.dot(feat, feat.T)
    return feat_gram


def gram_loss(feat, feat0, mask=1.):
    feat_size = feat.shape[:]
    N = feat_size[0]
    M = feat_size[1] * feat_size[2]
    feat_gram = gram(feat, mask)
    feat0_gram = gram(feat0, mask)
    feat = feat.reshape(N, M)
    loss = ((feat_gram - feat0_gram)**2).sum() / (4*(N**2)*(M**2))
    grad = np.dot((feat_gram - feat0_gram),
                  feat).reshape(feat_size) * mask / ((N**2)*(M**2))
    return loss, grad


def switch_loss_fun(loss_type):
    if loss_type == 'l2':
        return L2_loss
    elif loss_type == 'l1':
        return L1_loss
    elif loss_type == 'inner':
        return inner_loss
    elif loss_type == 'gram':
        return gram_loss
    else:
        raise ValueError('unknown loss function type!')


def img_preprocess(img, img_mean=np.float32([104, 117, 123])):
    '''convert to Caffe's input image layout'''
    return np.float32(np.transpose(img, (2, 0, 1))[::-1]) - np.reshape(img_mean, (3, 1, 1))


def img_deprocess(img, img_mean=np.float32([104, 117, 123])):
    '''convert from Caffe's input image layout'''
    return np.dstack((img + np.reshape(img_mean, (3, 1, 1)))[::-1])


def normalise_img(img):
    '''Normalize the image.
    Map the minimum pixel to 0; map the maximum pixel to 255.
    Convert the pixels to be int
    '''
    img = img - img.min()
    if img.max() > 0:
        img = img * (255.0/img.max())
    img = np.uint8(img)
    return img


def get_cnn_features(net, img, layer_list):
    '''Calculate the CNN features of the input image.
    Output the CNN features at layers in layer_list.
    The CNN features of multiple layers are assembled in a python dictionary, arranged in pairs of layer name (key) and CNN features (value).
    '''
    h, w = net.blobs['data'].data.shape[-2:]
    net.blobs['data'].reshape(1, 3, h, w)
    img_mean = net.transformer.mean['data']
    img = img_preprocess(img, img_mean)
    net.blobs['data'].data[0] = img
    net.forward()
    cnn_features = {}
    for layer in layer_list:
        feat = net.blobs[layer].data[0].copy()
        cnn_features[layer] = feat
    return cnn_features


def p_norm(x, p=2):
    '''p-norm loss and gradient'''
    loss = np.sum(np.abs(x) ** p)
    grad = p * (np.abs(x) ** (p-1)) * np.sign(x)
    return loss, grad


def TV_norm(x, TVbeta=1):
    '''TV_norm loss and gradient'''
    TVbeta = float(TVbeta)
    d1 = np.roll(x, -1, 1)
    d1[:, -1, :] = x[:, -1, :]
    d1 = d1 - x
    d2 = np.roll(x, -1, 2)
    d2[:, :, -1] = x[:, :, -1]
    d2 = d2 - x
    v = (np.sqrt(d1*d1 + d2*d2))**TVbeta
    loss = v.sum()
    v[v < 1e-5] = 1e-5
    d1_ = (v**(2*(TVbeta/2-1)/TVbeta)) * d1
    d2_ = (v**(2*(TVbeta/2-1)/TVbeta)) * d2
    d11 = np.roll(d1_, 1, 1) - d1_
    d22 = np.roll(d2_, 1, 2) - d2_
    d11[:, 0, :] = -d1_[:, 0, :]
    d22[:, :, 0] = -d2_[:, :, 0]
    grad = TVbeta * (d11 + d22)
    return loss, grad


def image_norm(img):
    '''calculate the norm of the RGB for each pixel'''
    img_norm = np.sqrt(img[0]**2 + img[1]**2 + img[2]**2)
    return img_norm


def gaussian_blur(img, sigma):
    '''smooth the image with gaussian filter'''
    if sigma > 0:
        img[0] = nd.filters.gaussian_filter(img[0], sigma, order=0)
        img[1] = nd.filters.gaussian_filter(img[1], sigma, order=0)
        img[2] = nd.filters.gaussian_filter(img[2], sigma, order=0)
    return img


def clip_extreme_value(img, pct=1):
    '''clip the pixels with extreme values'''
    if pct < 0:
        pct = 0.

    if pct > 100:
        pct = 100.

    img = np.clip(img, np.percentile(img, pct/2.),
                  np.percentile(img, 100-pct/2.))
    return img


def clip_small_norm_pixel(img, pct=1):
    '''clip pixels with small RGB norm'''
    if pct < 0:
        pct = 0.

    if pct > 100:
        pct = 100.

    img_norm = image_norm(img)
    small_pixel = img_norm < np.percentile(img_norm, pct)

    img[0][small_pixel] = 0
    img[1][small_pixel] = 0
    img[2][small_pixel] = 0
    return img


def clip_small_contribution_pixel(img, grad, pct=1):
    '''clip pixels with small contribution'''
    if pct < 0:
        pct = 0.

    if pct > 100:
        pct = 100.

    img_contribution = image_norm(img*grad)
    small_pixel = img_contribution < np.percentile(img_contribution, pct)

    img[0][small_pixel] = 0
    img[1][small_pixel] = 0
    img[2][small_pixel] = 0
    return img


def sort_layer_list(net, layer_list):
    '''sort layers in the list as the order in the net'''
    layer_index_list = []
    for layer in layer_list:
        # net.blobs is collections.OrderedDict
        for layer_index, layer0 in enumerate(net.blobs.keys()):
            if layer0 == layer:
                layer_index_list.append(layer_index)
                break
    layer_index_list_sorted = sorted(layer_index_list)
    #print("layer index list sorted : "+ str(layer_index_list_sorted))
    layer_list_sorted = []

    for layer_index in (layer_index_list_sorted):
        list_index = (layer_index_list.index(layer_index))
        #print(list_index)
        #print(type(layer_list))
        layer = list(layer_list)[list_index]
        #layer = list(layer_index_list.index(layer_index))
        layer_list_sorted.append(layer)
    return layer_list_sorted


def create_feature_masks(features, masks=None, channels=None):
    '''
    create feature mask for all layers;
    select CNN units using masks or channels
    input:
        features: a python dictionary consists of CNN features of target layers, arranged in pairs of layer name (key) and CNN features (value)
        masks: a python dictionary consists of masks for CNN features, arranged in pairs of layer name (key) and mask (value); the mask selects units for each layer to be used in the loss function (1: using the uint; 0: excluding the unit); mask can be 3D or 2D numpy array; use all the units if some layer not in the dictionary; setting to None for using all units for all layers
        channels: a python dictionary consists of channels to be selected, arranged in pairs of layer name (key) and channel numbers (value); the channel numbers of each layer are the channels to be used in the loss function; use all the channels if the some layer not in the dictionary; setting to None for using all channels for all layers
    output:
        feature_masks: a python dictionary consists of masks for CNN features, arranged in pairs of layer name (key) and mask (value); mask has the same shape as the CNN features of the corresponding layer;
    '''
    feature_masks = {}
    for layer in features.keys():
        if (masks is None or masks == {} or masks == [] or (layer not in masks.keys())) and (channels is None or channels == {} or channels == [] or (layer not in channels.keys())):  # use all features and all channels
            feature_masks[layer] = np.ones_like(features[layer])
        elif isinstance(masks, dict) and (layer in masks.keys()) and isinstance(masks[layer], np.ndarray) and masks[layer].ndim == 3 and masks[layer].shape[0] == features[layer].shape[0] and masks[layer].shape[1] == features[layer].shape[1] and masks[layer].shape[2] == features[layer].shape[2]:  # 3D mask
            feature_masks[layer] = masks[layer]
        # 1D feat and 1D mask
        elif isinstance(masks, dict) and (layer in masks.keys()) and isinstance(masks[layer], np.ndarray) and features[layer].ndim == 1 and masks[layer].ndim == 1 and masks[layer].shape[0] == features[layer].shape[0]:
            feature_masks[layer] = masks[layer]
        elif (masks is None or masks == {} or masks == [] or (layer not in masks.keys())) and isinstance(channels, dict) and (layer in channels.keys()) and isinstance(channels[layer], np.ndarray) and channels[layer].size > 0:  # select channels
            mask_2D = np.ones_like(features[layer][0])
            mask_3D = np.tile(mask_2D, [len(channels[layer]), 1, 1])
            feature_masks[layer] = np.zeros_like(features[layer])
            feature_masks[layer][channels[layer], :, :] = mask_3D
        # use 2D mask select features for all channels
        elif isinstance(masks, dict) and (layer in masks.keys()) and isinstance(masks[layer], np.ndarray) and masks[layer].ndim == 2 and (channels is None or channels == {} or channels == [] or (layer not in channels.keys())):
            mask_2D_0 = masks[layer]
            mask_size0 = mask_2D_0.shape
            mask_size = features[layer].shape[1:]
            if mask_size0[0] == mask_size[0] and mask_size0[1] == mask_size[1]:
                mask_2D = mask_2D_0
            else:
                mask_2D = np.ones(mask_size)
                n_dim1 = min(mask_size0[0], mask_size[0])
                n_dim2 = min(mask_size0[1], mask_size[1])
                idx0_dim1 = np.arange(n_dim1) + \
                    round((mask_size0[0] - n_dim1)/2)
                idx0_dim2 = np.arange(n_dim2) + \
                    round((mask_size0[1] - n_dim2)/2)
                idx_dim1 = np.arange(n_dim1) + round((mask_size[0] - n_dim1)/2)
                idx_dim2 = np.arange(n_dim2) + round((mask_size[1] - n_dim2)/2)
                mask_2D[idx_dim1, idx_dim2] = mask_2D_0[idx0_dim1, idx0_dim2]
            feature_masks[layer] = np.tile(
                mask_2D, [features[layer].shape[0], 1, 1])
        else:
            feature_masks[layer] = 0

    return feature_masks


def estimate_cnn_feat_std(cnn_feat):
    '''
    estimate the std of the CNN features
    INPUT:
        cnn_feat: CNN feature array [channel,dim1,dim2] or [1,channel];
    OUTPUT:
        cnn_feat_std: std of the CNN feature,
        here the std of each channel is estimated first,
        then average std across channels;
    '''
    feat_ndim = cnn_feat.ndim
    feat_size = cnn_feat.shape
    # for the case of fc layers
    if feat_ndim == 1 or (feat_ndim == 2 and feat_size[0] == 1) or (feat_ndim == 3 and feat_size[1] == 1 and feat_size[2] == 1):
        cnn_feat_std = np.std(cnn_feat)
    # for the case of conv layers
    elif feat_ndim == 3 and (feat_size[1] > 1 or feat_size[2] > 1):
        num_of_ch = feat_size[0]
        # std for each channel
        cnn_feat_std = np.zeros(num_of_ch, dtype='float32')
        for j in range(num_of_ch):
            feat_ch = cnn_feat[j, :, :]
            cnn_feat_std[j] = np.std(feat_ch)
        cnn_feat_std = np.mean(cnn_feat_std)  # std averaged across channels
    return cnn_feat_std

def reconstruct_image_icnn_lbfgs(features, net,
                      layer_weight=None, channel=None, mask=None, initial_image=None, loss_type='l2', maxiter=500, disp=True, save_intermediate=False, save_intermediate_every=1, save_intermediate_path=None,
                      save_intermediate_ext='jpg',
                      save_intermediate_postprocess=normalise_img):
    # loss function
    loss_fun = switch_loss_fun(loss_type)

    # make dir for saving intermediate
    if save_intermediate:
        if save_intermediate_path is None:
            save_intermediate_path = os.path.join('./recon_img_lbfgs_snapshots' + datetime.now().strftime('%Y%m%dT%H%M%S'))
        if not os.path.exists(save_intermediate_path):
            os.makedirs(save_intermediate_path)

    # image size
    img_size = net.blobs['data'].data.shape[-3:]

    # num of pixel
    num_of_pix = np.prod(img_size)

    # image mean
    img_mean = net.transformer.mean['data']

    # img bounds
    img_min = -img_mean
    img_max = img_min + 255.
    img_0 = np.array([img_min[0], img_max[0]])
    img_1 = np.array([img_min[1], img_max[1]])
    img_2 = np.array([img_min[2], img_max[2]])
    img_bounds = img_0*float(num_of_pix/3) + img_1*float(num_of_pix/3)+img_2*float(num_of_pix/3)
    img_bounds = img_bounds.squeeze()
    #print(img_bounds)
    # initial image
    if initial_image is None:
        initial_image = np.random.randint(0, 256, (img_size[1], img_size[2], img_size[0]))
    if save_intermediate:
        save_name = 'initial_img.png'
        PIL.Image.fromarray(np.uint8(initial_image)).save(os.path.join(save_intermediate_path, save_name))

    # preprocess initial img
    initial_image = img_preprocess(initial_image, img_mean)
    initial_image = initial_image.flatten()

    # layer_list
    layer_list = list(features.keys())
    print("layer list : "+ str(layer_list))
    layer_list = sort_layer_list(net, layer_list)
    print("layer list sorted : "+ str(layer_list))

    # number of layers
    num_of_layer = len(layer_list)

    # layer weight
    if layer_weight is None:
        weights = np.ones(num_of_layer)
        weights = np.float32(weights)
        weights = weights / weights.sum()
        layer_weight = {}
        for j, layer in enumerate(layer_list):
            layer_weight[layer] = weights[j]

    # feature mask
    feature_masks = create_feature_masks(features, masks=mask, channels=channel)

    # optimization params
    loss_list = []
    opt_params = {
        'args': (net, features, feature_masks, layer_weight, loss_fun, save_intermediate, save_intermediate_every, save_intermediate_path, save_intermediate_ext, save_intermediate_postprocess, loss_list),

        'method': 'L-BFGS-B',

        'jac': True,

        'bounds': img_bounds,

        'options': {'maxiter': maxiter, 'disp': disp},
    }

    # optimization
    res = minimize(obj_fun, initial_image, args = (net, features, feature_masks, layer_weight, loss_fun, save_intermediate, save_intermediate_every, save_intermediate_path, save_intermediate_ext,
                                                   save_intermediate_postprocess, loss_list), 
                   method='L-BFGS-B', jac=True, options= {'maxiter': maxiter})
    #,bounds=img_bounds)

    # recon img
    img = res.x
    img = img.reshape(img_size)

    # return img
    return img_deprocess(img, img_mean), loss_list


def obj_fun(img, net, features, feature_masks, layer_weight, loss_fun, save_intermediate, save_intermediate_every, save_intermediate_path, save_intermediate_ext, save_intermediate_postprocess, loss_list=[]):
    # reshape img
    img_size = net.blobs['data'].data.shape[-3:]
    img = img.reshape(img_size)

    # save intermediate image
    t = len(loss_list)
    if save_intermediate and (t % save_intermediate_every == 0):
        img_mean = net.transformer.mean['data']
        save_path = os.path.join(save_intermediate_path, '%05d.%s' % (t, save_intermediate_ext))
        if save_intermediate_postprocess is None:
            snapshot_img = img_deprocess(img, img_mean)
        else:
            snapshot_img = save_intermediate_postprocess(img_deprocess(img, img_mean))
        PIL.Image.fromarray(snapshot_img).save(save_path)

    # layer_list
    layer_list = features.keys()
    layer_list = sort_layer_list(net, layer_list)

    # num_of_layer
    num_of_layer = len(layer_list)

    # cnn forward
    net.blobs['data'].data[0] = img.copy()
    net.forward(end=layer_list[-1])

    # cnn backward
    loss = 0.
    layer_start = layer_list[-1]
    net.blobs[layer_start].diff.fill(0.)
    for j in range(num_of_layer):
        layer_start_index = num_of_layer - 1 - j
        layer_end_index = num_of_layer - 1 - j - 1
        layer_start = layer_list[layer_start_index]
        if layer_end_index >= 0:
            layer_end = layer_list[layer_end_index]
        else:
            layer_end = 'data'
        feat_j = net.blobs[layer_start].data[0].copy()
        feat0_j = features[layer_start]
        mask_j = feature_masks[layer_start]
        layer_weight_j = layer_weight[layer_start]
        loss_j, grad_j = loss_fun(feat_j, feat0_j, mask_j)
        loss_j = layer_weight_j * loss_j
        grad_j = layer_weight_j * grad_j
        loss = loss + loss_j
        g = net.blobs[layer_start].diff[0].copy()
        g = g + grad_j
        net.blobs[layer_start].diff[0] = g.copy()
        if layer_end == 'data':
            net.backward(start=layer_start)
        else:
            net.backward(start=layer_start, end=layer_end)
        net.blobs[layer_start].diff.fill(0.)
    grad = net.blobs['data'].diff[0].copy()

    # reshape gradient
    grad = grad.flatten().astype(np.float64)

    loss_list.append(loss)

    return loss, grad


# GPU
caffe.set_mode_gpu()
caffe.set_device(0)

# Decoded features settings
decoded_features_dir = './data/decodedfeatures'
decode_feature_filename = lambda net, layer, subject, roi, image_type, image_label: os.path.join(decoded_features_dir, image_type, net, layer, subject, roi,
                                                                                                 '%s-%s-%s-%s-%s-%s.mat' % (image_type, net, layer, subject, roi, image_label))

# Data settings
results_dir = './results'

subjects_list = ['S1', 'S2', 'S3']

rois_list = ['VC']

network = 'VGG19'

# DNN layer combinations
layers_sets = {'layers-1to1' : ['conv1_1', 'conv1_2'],
               'layers-1to3' : ['conv1_1', 'conv1_2', 'conv2_1', 'conv2_2',
                                'conv3_1', 'conv3_2', 'conv3_3', 'conv3_4'],
               'layers-1to5' : ['conv1_1', 'conv1_2', 'conv2_1', 'conv2_2',
                                'conv3_1', 'conv3_2', 'conv3_3', 'conv3_4',
                                'conv4_1', 'conv4_2', 'conv4_3', 'conv4_4',
                                'conv5_1', 'conv5_2', 'conv5_3', 'conv5_4'],
               'layers-1to7' : ['conv1_1', 'conv1_2', 'conv2_1', 'conv2_2',
                                'conv3_1', 'conv3_2', 'conv3_3', 'conv3_4',
                                'conv4_1', 'conv4_2', 'conv4_3', 'conv4_4',
                                'conv5_1', 'conv5_2', 'conv5_3', 'conv5_4',
                                'fc6', 'fc7']}

# Images in figure 4
'''image_type = 'natural'
image_label_list = ['Img0016',
                    'Img0036',
                    'Img0042']'''

image_type = 'alphabet'
image_label_list = ['Img0005']

max_iteration = 200

# Average image of ImageNet
img_mean_file = '/content/DeepImageReconstruction/data/ilsvrc_2012_mean.npy'
img_mean = np.load(img_mean_file)
img_mean = np.float32([img_mean[0].mean(), img_mean[1].mean(), img_mean[2].mean()])

# load CNN
model_file = '/content/DeepImageReconstruction/net/VGG_ILSVRC_19_layers/VGG_ILSVRC_19_layers.caffemodel'
prototxt_file = '/content/DeepImageReconstruction/net/VGG_ILSVRC_19_layers/VGG_ILSVRC_19_layers.prototxt'
channel_swap = (2, 1, 0)
net = caffe.Classifier(prototxt_file, model_file, mean=img_mean, channel_swap=channel_swap)
h, w = net.blobs['data'].data.shape[-2:]
net.blobs['data'].reshape(1, 3, h, w)

# Initial image for the optimization 
initial_image = np.zeros((h, w, 3), dtype='float32')
initial_image[:, :, 0] = img_mean[2].copy()
initial_image[:, :, 1] = img_mean[1].copy()
initial_image[:, :, 2] = img_mean[0].copy()

# Feature SD
feat_std_file = '/content/DeepImageReconstruction/data/estimated_vgg19_cnn_feat_std.mat'
feat_std0 = sio.loadmat(feat_std_file)

# CNN Layers (all conv and fc layers)
#layers = [layer for layer in net.blobs.keys() if 'conv' in layer or 'fc' in layer]

# Setup results directory ----------------------------------------------------

save_dir_root = os.path.join(results_dir)#, os.path.splitext(file)[0])
if not os.path.exists(save_dir_root):
    os.makedirs(save_dir_root)

# Set reconstruction options -------------------------------------------------

opts = {
    # The loss function type: {'l2','l1','inner','gram'}
    'loss_type': 'l2',

    # The maximum number of iterations
    'maxiter': max_iteration,

    # The initial image for the optimization (setting to None will use random noise as initial image)
    'initial_image': initial_image,

    # Display the information on the terminal or not
    'disp': True
}

# Save the optional parameters
with open(os.path.join(save_dir_root, 'options.pkl'), 'wb') as f:
    pickle.dump(opts, f)

# Reconstrucion --------------------------------------------------------------

for subject, roi, image_label, (layers_set, layers) in product(subjects_list, rois_list, image_label_list, layers_sets.items()):

    print('')
    print('Subject:     ' + subject)
    print('ROI:         ' + roi)
    print('Image label: ' + image_label)
    print('')

    save_dir = os.path.join(save_dir_root, layers_set, subject, roi)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # Load the decoded CNN features
    features = {}
    for layer in layers:
        # The file full name depends on the data structure for decoded CNN features
        colab_path = "DeepImageReconstruction"
        file_name = decode_feature_filename(network, layer, subject, roi, image_type, image_label)
        file_name = file_name.strip(".")
        file_name = colab_path+file_name
        #file_name = os.path.join(colab_path, file_name)
        print(file_name)
        feat = sio.loadmat(file_name)['feat']
        if 'fc' in layer:
            feat = feat.reshape(feat.size)

        # Correct the norm of the decoded CNN features
        feat_std = estimate_cnn_feat_std(feat)
        feat = (feat / feat_std) * feat_std0[layer]

        features.update({layer: feat})

    # Weight of each layer in the total loss function

    # Norm of the CNN features for each layer
    feat_norm = np.array([np.linalg.norm(features[layer]) for layer in layers], dtype='float32')

    # Use the inverse of the squared norm of the CNN features as the weight for each layer
    weights = 1. / (feat_norm ** 2)

    # Normalise the weights such that the sum of the weights = 1
    weights = weights / weights.sum()
    layer_weight = dict(zip(layers, weights))

    opts.update({'layer_weight': layer_weight})

    #print(opts)
    # Reconstruction
    snapshots_dir = os.path.join(save_dir, 'snapshots', 'image-%s' % image_label)
    recon_img, loss_list = reconstruct_image_icnn_lbfgs(features, net,
                                             save_intermediate=True,
                                             save_intermediate_path=snapshots_dir,
                                             **opts)

    # Save the results

    # Save the raw reconstructed image
    save_name = 'recon_img' + '-' + image_label + '.mat'
    sio.savemat(os.path.join(save_dir, save_name), {'recon_img': recon_img})

    # To better display the image, clip pixels with extreme values (0.02% of
    # pixels with extreme low values and 0.02% of the pixels with extreme high
    # values). And then normalise the image by mapping the pixel value to be
    # within [0,255].
    save_name = 'recon_img_normalized' + '-' + image_label + '.jpg'
    PIL.Image.fromarray(normalise_img(clip_extreme_value(recon_img, pct=0.04))).save(os.path.join(save_dir, save_name))

print('Done')