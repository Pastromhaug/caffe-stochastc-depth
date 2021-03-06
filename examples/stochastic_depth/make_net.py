from __future__ import print_function
from caffe import layers as L, params as P, to_proto
from caffe.proto import caffe_pb2
import caffe
import numpy as np
import matplotlib.pyplot as plt 
import time
import datetime
from PIL import Image
import sys
sys.setrecursionlimit(150000)

# helper function for common structures
def log():
    print ('device: ', device)
    print ('stages: ', stages)
    print ('deathRate: ', deathRate)
    print ('niter: ', niter)
    print ('lr: ', lr)
    print ('real: ', real)

def conv_factory(bottom, ks, nout, stride=1, pad=0):
    conv = L.Convolution(bottom, kernel_size=ks, stride=stride,
                                num_output=nout, pad=pad, bias_term=True, weight_filler=dict(type='msra'), bias_filler=dict(type='constant'))
    batch_norm = L.BatchNorm(conv, in_place=True, param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0)])
    scale = L.Scale(batch_norm, bias_term=True, in_place=True)
    return scale

def conv_factory_relu(bottom, ks, nout, stride=1, pad=0):
    conv = L.Convolution(bottom, kernel_size=ks, stride=stride,
                                num_output=nout, pad=pad, bias_term=True, weight_filler=dict(type='msra'), bias_filler=dict(type='constant'))
    batch_norm = L.BatchNorm(conv, in_place=True, param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0)])
    scale = L.Scale(batch_norm, bias_term=True, in_place=True)
    relu = L.ReLU(scale, in_place=True)
    return relu

#written by me
def residual_factory1(bottom, num_filter):
    conv1 = conv_factory_relu(bottom, 3, num_filter, 1, 1)
    conv2 = conv_factory(conv1, 3, num_filter, 1, 1)
    addition = L.Eltwise(bottom, conv2, operation=P.Eltwise.SUM)
    relu = L.ReLU(addition, in_place=True)
    return relu

#written by me
def residual_factory_padding1(bottom, num_filter, stride, batch_size, feature_size):
    conv1 = conv_factory_relu(bottom, ks=3, nout=num_filter, stride=stride, pad=1)
    conv2 = conv_factory(conv1, ks=3, nout=num_filter, stride=1, pad=1)
    pool1 = L.Pooling(bottom, pool=P.Pooling.AVE, kernel_size=2, stride=2)
    padding = L.Input(input_param=dict(shape=dict(dim=[batch_size, num_filter/2, feature_size, feature_size])))
    concate = L.Concat(pool1, padding, axis=1)
    addition = L.Eltwise(concate, conv2, operation=P.Eltwise.SUM)
    relu = L.ReLU(addition, in_place=True)
    return relu


def resnet(leveldb, batch_size=128, stages=[2, 2, 2, 2], first_output=16):
    feature_size=32
    data, label = L.Data(source=leveldb, backend=P.Data.LEVELDB, batch_size=batch_size, ntop=2,
        transform_param=dict(crop_size=feature_size, mirror=True))
    residual = conv_factory_relu(data, 3, first_output, stride=1, pad=1)
    
    st = 0
    for i in stages[1:]:
        st += 1
        for j in range(i):
            if j==i-1:
                first_output *= 2
                feature_size /= 2
                if i==0:
                    residual = residual_factory_proj(residual, first_output, 1)
                # bottleneck layer, but not at the last stage
                elif st != 3:
                    if real:
                        residual = residual_factory_padding1(residual, num_filter=first_output, stride=2, 
                            batch_size=batch_size, feature_size=feature_size)
                    else:
                        residual = residual_factory_padding2(residual, num_filter=first_output, stride=2, 
                            batch_size=batch_size, feature_size=feature_size)
            else:
                if real:
                    residual = residual_factory1(residual, first_output)
                else:
                    residual = residual_factory2(residual, first_output)


    glb_pool = L.Pooling(residual, pool=P.Pooling.AVE, global_pooling=True);
    fc = L.InnerProduct(glb_pool, num_output=10,bias_term=True, weight_filler=dict(type='msra'))
    loss = L.SoftmaxWithLoss(fc, label)
    return to_proto(loss)

def make_net(stages, device):

    with open('examples/resnet_cifar/residual_train.prototxt', 'w') as f:
        print(str(resnet('examples/cifar10/cifar10_train_leveldb_padding' + str(device), stages=stages, batch_size=128)), file=f)

    with open('examples/resnet_cifar/residual_test.prototxt', 'w') as f:
        print(str(resnet('examples/cifar10/cifar10_test_leveldb_padding' + str(device), stages=stages, batch_size=100)), file=f)

def make_solver(niter=20000, lr = 0.1):
    s = caffe_pb2.SolverParameter()
    s.random_seed = 0xCAFFE

    s.train_net = 'examples/resnet_cifar/residual_train.prototxt'
    s.test_net.append('examples/resnet_cifar/residual_test.prototxt')
    s.test_interval = 10000
    s.test_iter.append(100)

    s.max_iter = niter
    s.type = 'Nesterov'
    s.display = 200

    s.base_lr = lr
    s.momentum = 0.9
    s.weight_decay = 1e-4

    s.lr_policy='multistep'
    s.gamma = 0.1
    s.stepvalue.append(int(0.5 * s.max_iter))
    s.stepvalue.append(int(0.75 * s.max_iter))
    s.solver_mode = caffe_pb2.SolverParameter.GPU

    solver_path = 'examples/resnet_cifar/solver.prototxt'
    with open(solver_path, 'w') as f:
        f.write(str(s))

device = 2
niter = 200000
N=18
stages = [2, N+1, N, N]
deathRate = 0
lr = 0.1
real = True


make_net(stages, device)
make_solver(niter=niter)










