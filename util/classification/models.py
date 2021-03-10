import tensorflow as tf
from tensorflow.keras import Sequential
from tensorflow.keras.models import Model, Sequential
from tensorflow.keras.optimizers import SGD, Adam
from tensorflow.keras.layers import Input, Add, Dense, Dropout, Activation, ZeroPadding2D, Flatten, Conv2D, AveragePooling2D, MaxPooling2D, GlobalMaxPooling2D
from tensorflow.keras.layers.experimental.preprocessing import RandomFlip
from string import ascii_lowercase

# Custom layers.
from util.keras.layers import *

# Our baseline, fully-connected neural network for classification.
# Operates on a single vector (e.g. flattened image from one calorimeter layer).
# Optionally uses dropouts between layers.
class baseline_nn_model(): 
    def __init__(self, strategy, number_pixels, lr=5e-5, dropout=-1):
        self.strategy = strategy
        self.dropout = dropout
        self.number_pixels = number_pixels
        self.lr = lr
        self.custom_objects = {}
    
    # create model
    def model(self):
        dropout = self.dropout
        used_pixels = self.number_pixels
        strategy = self.strategy
        lr = self.lr
        with strategy.scope():    
            model = Sequential()
            model.add(Dense(used_pixels, input_dim=used_pixels, kernel_initializer='normal', activation='relu'))
            if(self.dropout > 0.): model.add(Dropout(dropout))
            model.add(Dense(used_pixels, activation='relu'))
            if(self.dropout > 0.): model.add(Dropout(dropout))
            model.add(Dense(int(used_pixels/2), activation='relu'))
            if(self.dropout > 0.): model.add(Dropout(dropout))
            model.add(Dense(2, kernel_initializer='normal', activation='softmax'))
            # compile model
            optimizer = Adam(lr=lr)
            model.compile(loss='categorical_crossentropy', optimizer=optimizer, metrics=['acc'])
        return model
    
# A simple implementation of ResNet.
# As input, this takes multiple images, which may be of different sizes,
# and they are all rescaled to a user-specified size.
class resnet(): 
    def __init__(self, filter_sets, f_vals, s_vals, i_vals, channels=6, lr=5e-5, input_shape = (128,16), augmentation=True, normalization=True, classes=2):
        self.filter_sets = filter_sets
        self.f_vals = f_vals
        self.s_vals = s_vals
        self.i_vals = i_vals
        self.channels = channels
        self.input_shape = input_shape
        self.augmentation = augmentation
        self.normalization = normalization
        self.lr = lr
        self.classes = classes
        self.custom_objects = {
            'ImageScaleBlock':ImageScaleBlock,
            'ConvolutionBlock':ConvolutionBlock,
            'IdentityBlock':IdentityBlock
        }
    
    # create model
    def model(self):
        filter_sets = self.filter_sets
        f_vals = self.f_vals
        s_vals = self.s_vals
        i_vals = self.i_vals
        channels = self.channels
        input_shape = self.input_shape
        augmentation = self.augmentation
        normalization = self.normalization
        lr = self.lr
        classes = self.classes
        
        # Input images -- one for each channel, each channel's dimensions may be different.
        inputs = [Input((None,None,1),name='input'+str(i)) for i in range(channels)]

        # Rescale all the input images, so that their dimensions now match.
        # Note that we make sure to re-normalize the images so that we preserve their energies.
        X = ImageScaleBlock(input_shape,normalization=True,name_prefix='scaled_input_')(inputs)
        #X = image_scale_block(inputs, input_shape, normalization=normalization, name_prefix = 'scaled_input_')
        X = ZeroPadding2D((3,3))(X)

        # Data augmentation.
        # With channels combined, we can now flip images in (eta,phi, eta&phi).
        # Note that these flips will not require making any changes to
        # the other inputs (energy, abs(eta)), so the augmentation is
        # as simple as flipping the images using built-in functions.
        # These augmentation functions will only be active during training.
        if(augmentation): X = RandomFlip(name='aug_reflect')(X)

        # Stage 1
        X = Conv2D(64, (7, 7), strides=(2, 2), name='conv1', kernel_initializer=glorot_uniform(seed=0))(X)
        X = BatchNormalization(axis=3, name='bn_conv1')(X)
        X = Activation('relu')(X)
        X = MaxPooling2D((3, 3), strides=(2, 2))(X)
       
        n = len(f_vals)
        for i in range(n):
            filters = filter_sets[i]
            f = f_vals[i]
            s = s_vals[i]
            ib = i_vals[i]
            stage = i + 1 # 1st stage is Conv2D etc. before ResNet blocks
            #X = convolutional_block(X, f=f, filters=filters, stage=stage, block='a', s=1)
            X = ConvolutionBlock(f=f, filters=filters, stage=stage, block='a', s=s, normalization=normalization)(X)
            
            for j in range(ib):
                #X = identity_block(X, f, filters, stage=stage, block=ascii_lowercase[j+1]) # will only cause naming issues if there are many id blocks
                X = IdentityBlock(f=f, filters=filters, stage=stage, block=ascii_lowercase[j+1],normalization=normalization)(X)

        # AVGPOOL
        pool_size = (2,2)
        if(X.shape[1] == 1):   pool_size = (1,2)
        elif(X.shape[2] == 1): pool_size = (2,1)
        X = AveragePooling2D(pool_size=pool_size, name="avg_pool")(X)

        # output layer
        X = Flatten()(X)
        X = Dense(classes, activation='softmax', name='fc' + str(classes), kernel_initializer = glorot_uniform(seed=0))(X)

        # Create model object.
        model = Model(inputs=inputs, outputs=X, name='ResNet50')

        # Compile the model
        optimizer = Adam(lr=lr)
        model.compile(loss='categorical_crossentropy', optimizer=optimizer, metrics=['acc'])
        return model

# A simple combination network -- in practice we may use this to
# "combine" classification scores from single calo-layer networks.
class simple_combine_model(): 
    def __init__(self, strategy, lr=5e-5, n_input=6):
        self.strategy = strategy
        self.n_input = n_input
        self.lr = lr
        self.custom_objects = {}
    
    # create model
    def model(self):
        n_input = self.n_input
        strategy = self.strategy
        lr = self.lr
        with strategy.scope():
            model = Sequential()
            model.add(Dense(n_input, input_dim=n_input, kernel_initializer='normal', activation='relu'))
            model.add(Dense(4, activation='relu'))
            model.add(Dense(2, kernel_initializer='normal', activation='softmax'))
            # compile model
            optimizer = Adam(lr=lr)
            model.compile(loss='categorical_crossentropy', optimizer=optimizer, metrics=['acc'])
        return model

