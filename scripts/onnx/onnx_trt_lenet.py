#--*-- coding:utf-8 --*--
import pycuda.autoinit 
import pycuda.driver as cuda
import tensorrt as trt
#import torch 
import time 
from PIL import Image
import cv2,os
#import torchvision 
import numpy as np

filename = '/home/zwzhou/Code/img.png'
max_batch_size = 1
onnx_model_path = "./lenet_opt11.onnx"

TRT_LOGGER = trt.Logger()
    
def get_img_np_nchw(filename): # -> read grayscale image
    #image_cv = cv2.imread(filename, cv2.IMREAD_GRAYSCALE)
    image_cv = np.zeros((28,28), dtype=np.float32)
    img_np = np.array(image_cv, dtype=np.float)/255.
    img_np_nchw = np.expand_dims(np.expand_dims(np.squeeze(img_np), 0), 0)
    return img_np_nchw

class HostDeviceMem(object):
    def __init__(self, host_mem, device_mem):
        """
        host_mem: cpu memory
        device_mem: gpu memory
        """
        self.host = host_mem
        self.device = device_mem

    def __str__(self):
        return "Host:\n" + str(self.host)+"\nDevice:\n"+str(self.device)

    def __repr__(self):
        return self.__str__()

def allocate_buffers(engine):
    inputs, outputs, bindings = [], [], []
    stream = cuda.Stream()
    for binding in engine:
        # print(binding) # 绑定的输入输出
        # print(engine.get_binding_shape(binding)) # get_binding_shape 是变量的大小
        size = trt.volume(engine.get_binding_shape(binding))*engine.max_batch_size
        # volume 计算可迭代变量的空间，指元素个数
        # size = trt.volume(engine.get_binding_shape(binding)) # 如果采用固定bs的onnx，则采用该句
        dtype = trt.nptype(engine.get_binding_dtype(binding))
        # get_binding_dtype  获得binding的数据类型
        # nptype等价于numpy中的dtype，即数据类型
        # allocate host and device buffers
        host_mem = cuda.pagelocked_empty(size, dtype)  # 创建锁业内存
        device_mem = cuda.mem_alloc(host_mem.nbytes)    # cuda分配空间
        # print(int(device_mem)) # binding在计算图中的缓冲地址
        bindings.append(int(device_mem))
        #append to the appropriate list
        if engine.binding_is_input(binding):
            inputs.append(HostDeviceMem(host_mem, device_mem))
        else:
            outputs.append(HostDeviceMem(host_mem, device_mem))
    return inputs, outputs, bindings, stream
    
    
def get_engine(max_batch_size=1, onnx_file_path="", engine_file_path="", fp16_mode=False, save_engine=False):
    '''
    通过加载onnx文件，构建engine
    :param onnx_file_path: onnx文件路径
    :return: engine
    '''
    # 打印日志
    _LOGGER = trt.Logger(trt.Logger.WARNING)
    
    # 如果已经存在序列化之后的引擎，则直接反序列化得到cudaEngine
    if os.path.exists(engine_file_path):
        print("Reading engine from file: {}".format(engine_file_path))
        with open(engine_file_path, 'rb') as f, \
            trt.Runtime(TRT_LOGGER) as runtime:
            return runtime.deserialize_cuda_engine(f.read())  # 反序列化
 
    with trt.Builder(TRT_LOGGER) as builder, builder.create_network() as network, trt.OnnxParser(network, TRT_LOGGER) as parser:
        builder.fp16_mode = fp16_mode
        builder.max_batch_size = max_batch_size
        builder.max_workspace_size = 1 << 20
 
    print('Loading ONNX file from path {}...'.format(onnx_file_path))
    with open(onnx_file_path, 'rb') as model:
        print('Beginning ONNX file parsing')
        parser.parse(model.read())
        print('Completed parsing of ONNX file')
 
    print('Building an engine from file {}; this may take a while...'.format(onnx_file_path))
    engine = builder.build_cuda_engine(network)
    print("Completed creating Engine")
    
    if save_engine:  #保存engine供以后直接反序列化使用
        with open(engine_file_path, 'wb') as f: f.write(engine.serialize())  # 序列化
 
    # 保存计划文件
    # with open(engine_file_path, "wb") as f:
    #  f.write(engine.serialize())
    return engine
    

'''
def get_engine(max_batch_size=1, onnx_file_path="", engine_file_path="",fp16_mode=False, save_engine=False):
    """
    params max_batch_size:      预先指定大小好分配显存
    params onnx_file_path:      onnx文件路径
    params engine_file_path:    待保存的序列化的引擎文件路径
    params fp16_mode:           是否采用FP16
    params save_engine:         是否保存引擎
    returns:                    ICudaEngine
    """
    # 如果已经存在序列化之后的引擎，则直接反序列化得到cudaEngine
    if os.path.exists(engine_file_path):
        print("Reading engine from file: {}".format(engine_file_path))
        with open(engine_file_path, 'rb') as f, \
            trt.Runtime(TRT_LOGGER) as runtime:
            return runtime.deserialize_cuda_engine(f.read())  # 反序列化
    else:  # 由onnx创建cudaEngine
        
        # 使用logger创建一个builder 
        # builder创建一个计算图 INetworkDefinition
        explicit_batch = 1 << (int)(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        # In TensorRT 7.0, the ONNX parser only supports full-dimensions mode, meaning that your network definition must be created with the explicitBatch flag set. For more information, see Working With Dynamic Shapes.

        with trt.Builder(TRT_LOGGER) as builder, \
            builder.create_network(explicit_batch) as network,  \
            trt.OnnxParser(network, TRT_LOGGER) as parser: # 使用onnx的解析器绑定计算图，后续将通过解析填充计算图
            builder.max_workspace_size = 1<<30  # 预先分配的工作空间大小,即ICudaEngine执行时GPU最大需要的空间
            builder.max_batch_size = max_batch_size # 执行时最大可以使用的batchsize
            builder.fp16_mode = fp16_mode

            # 解析onnx文件，填充计算图
            if not os.path.exists(onnx_file_path):
                quit("ONNX file {} not found!".format(onnx_file_path))
            print('loading onnx file from path {} ...'.format(onnx_file_path))
            with open(onnx_file_path, 'rb') as model: # 二值化的网络结果和参数
                print("Begining onnx file parsing")
                parser.parse(model.read())  # 解析onnx文件
            #parser.parse_from_file(onnx_file_path) # parser还有一个从文件解析onnx的方法

            print("Completed parsing of onnx file")
            # 填充计算图完成后，则使用builder从计算图中创建CudaEngine
            print("Building an engine from file{}' this may take a while...".format(onnx_file_path))

            #################
            print(network.get_layer(network.num_layers-1).get_output(0).shape)
            # network.mark_output(network.get_layer(network.num_layers -1).get_output(0))
            engine=builder.build_cuda_engine(network)  # 注意，这里的network是INetworkDefinition类型，即填充后的计算图
            print("Completed creating Engine")
            if save_engine:  #保存engine供以后直接反序列化使用
                with open(engine_file_path, 'wb') as f:
                    f.write(engine.serialize())  # 序列化
            return engine
'''

def do_inference(context, bindings, inputs, outputs, stream, batch_size=1):
    # Transfer data from CPU to the GPU.
    [cuda.memcpy_htod_async(inp.device, inp.host, stream) for inp in inputs]
    # htod： host to device 将数据由cpu复制到gpu device
    # Run inference.
    context.execute_async_v2(bindings=bindings, stream_handle=stream.handle)
    # 当创建network时显式指定了batchsize， 则使用execute_async_v2, 否则使用execute_async
    # Transfer predictions back from the GPU.
    [cuda.memcpy_dtoh_async(out.host, out.device, stream) for out in outputs]
    # gpu to cpu
    # Synchronize the stream
    stream.synchronize()
    # Return only the host outputs.
    return [out.host for out in outputs]

def postprocess_the_outputs(h_outputs, shape_of_output):
    h_outputs = h_outputs.reshape(*shape_of_output)
    return h_outputs

img_np_nchw = get_img_np_nchw(filename).astype(np.float32)
#These two modes are depend on hardwares
fp16_mode = False
trt_engine_path = "./model_fp16_{}.trt".format(fp16_mode)
# Build an cudaEngine
engine = get_engine(max_batch_size, onnx_model_path, trt_engine_path, fp16_mode)
# 创建CudaEngine之后,需要将该引擎应用到不同的卡上配置执行环境
context = engine.create_execution_context()
inputs, outputs, bindings, stream = allocate_buffers(engine) # input, output: host # bindings

# Do inference
shape_of_output = (max_batch_size, 1000)
# Load data to the buffer
inputs[0].host = img_np_nchw.reshape(-1)

# inputs[1].host = ... for multiple input
t1 = time.time()
trt_outputs = do_inference(context, bindings=bindings, inputs=inputs, outputs=outputs, stream=stream) # numpy data
t2 = time.time()
feat = postprocess_the_outputs(trt_outputs[0], shape_of_output)

print('TensorRT ok')

# model = torchvision.models.resnet18(pretrained=True).cuda()
# resnet_model = model.eval()
# input_for_torch = torch.from_numpy(img_np_nchw).cuda()
# t3 = time.time()
# feat_2= resnet_model(input_for_torch)
# t4 = time.time()
# feat_2 = feat_2.cpu().data.numpy()
# print('Pytorch ok!')

# mse = np.mean((feat - feat_2)**2)
# print("Inference time with the TensorRT engine: {}".format(t2-t1))
# print("Inference time with the PyTorch model: {}".format(t4-t3))
# print('MSE Error = {}'.format(mse))

# print('All completed!')
