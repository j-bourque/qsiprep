#!python
from __future__ import print_function

from nipype.interfaces.base import (TraitedSpec, CommandLineInputSpec, BaseInterfaceInputSpec,
                                    CommandLine, File, traits, isdefined, SimpleInterface,
                                    InputMultiObject, OutputMultiObject)

import os
import os.path as op
from glob import glob
from nipype.utils.filemanip import fname_presuffix, split_filename
import logging
from copy import deepcopy
import numpy as np
from scipy.io.matlab import loadmat, savemat
import nibabel as nb
LOGGER = logging.getLogger('nipype.interface')


# Step 1 from DSI Studio, importing DICOM files or nifti
class MultivariateTemplateConstruction2InputSpec(CommandLineInputSpec):
    dimension = traits.Enum(2, 3, 4, default=3, usedefault=True, argstr='-d %d')
    input_file = File(
        desc="txt or csv file with images",
        exists=True,
        position=-1)
    input_images = InputMultiObject(
        traits.Either(File(exists=True), InputMultiObject(File(exists=True))),
        desc='list of images or lists of images',
        xor=('input_file',),
        argstr='%s',
        position=-1,
        copyfile=False)
    image_statistic = traits.Enum(
        0, 1, 2, default=1, usedefault=True, desc='statistic used to summarize '
        'images. 0=mean, 1= mean of normalized intensities, 2=median')
    iteration_limit = traits.Int(4, usedefault=True, argstr='-i %d',
                                 desc='maximum number of iterations')
    backup_images = traits.Bool(False, argstr='-b %d')
    parallel_control = traits.Enum(
        0, 1, 2, 3, 4, 5, desc='Control for parallel computation '
        '0 = run serially, '
        '1 = SGE qsub, '
        '2 = use PEXEC (localhost), '
        '3 = Apple XGrid, '
        '4 = PBS qsub, '
        '5 = SLURM',
        argstr='-c %d',
        usedefault=True,
        hash_files=False)
    num_cores = traits.Int(default=1, usedefault=True, argstr='-j %d', hash_files=False)
    num_modalities = traits.Int(
        1, usedefault=True, desc='Number of modalities used '
        'to construct the template (default 1):  For example, '
        'if one wanted to create a multimodal template consisting of T1,T2,and FA '
        'components ("-k 3")', argstr='-k %d')
    modality_weights = traits.List([1], usedefault=True)
    n4_bias_correct = traits.Bool(True, usedefault=True, argstr='-n %d')
    metric = traits.Str('CC', usedefault=True, argstr='-m %s', mandatory=True)
    transform = traits.Enum('BSplineSyN', 'SyN', 'Affine', usedefault=True,
                            argstr='-t %s', mandatory=True)
    output_prefix = traits.Str('antsBTP')
    gradient_step = traits.Float(0.25, usedefault=True, mandatory=True, argstr='-g %.3f')
    usefloat = traits.Bool(True, argstr='-e %d', usedefault=True)


class MultivariateTemplateConstruction2OutputSpec(TraitedSpec):
    templates = OutputMultiObject(File(exists=True), mandatory=True)
    forward_transforms = OutputMultiObject(
        OutputMultiObject(File(exists=True)), mandatory=True)
    reverse_transforms = OutputMultiObject(
        OutputMultiObject(File(exists=True)), mandatory=True)
    iteration_templates = OutputMultiObject(File(exists=True))

class MultivariateTemplateConstruction2(CommandLine):
    input_spec = MultivariateTemplateConstruction2InputSpec
    output_spec = MultivariateTemplateConstruction2OutputSpec
    _cmd = "antsMultivariateTemplateConstruction2.sh "

    def _format_arg(self, opt, spec, val):
        if opt == 'input_images':
            return ' '.join([op.split(fname)[1] for fname in val])
        if opt == 'modality_weights':
            return 'x'.join(['%.3f' % weight for weight in val])
        return super(MultivariateTemplateConstruction2, self)._format_arg(opt, spec, val)

    def _list_outputs(self):
        if isdefined(self.inputs.input_file):
            raise NotImplementedError()
        forward_transforms = []
        reverse_transforms = []
        if isdefined(self.inputs.output_prefix):
            prefix = self.inputs.output_prefix
        else:
            prefix = "antsBTP"
        cwd = os.getcwd()
        for num, input_image in enumerate(self.inputs.input_images):
            if isinstance(input_image, list):
                input_image = input_image[0]
            path, fname, ext = split_filename(input_image)
            affine = '%s/%s%s%d0GenericAffine.mat' % (cwd, prefix, fname, num)
            warp = '%s/%s%s%d1Warp.nii.gz' % (cwd, prefix, fname, num)
            inv_warp = '%s/%s%s%d1InverseWarp.nii.gz' % (cwd, prefix, fname, num)
            forward_transforms.append([affine, warp])
            reverse_transforms.append([inv_warp, affine])

        templates = ['%s/%stemplate%s.nii.gz' % (cwd, prefix, tnum)
                     for tnum in range(self.inputs.num_modalities)]
        outputs = self.output_spec().get()
        outputs["forward_transforms"] = forward_transforms
        outputs["reverse_transforms"] = reverse_transforms
        outputs["templates"] = templates

        return outputs