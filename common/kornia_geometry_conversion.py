import torch
import torch.nn as nn
import torch.nn.functional as F

from numpy import pi

__all__ = [
    # functional api
    "rad2deg",
    "deg2rad",
    "convert_points_from_homogeneous",
    "convert_points_to_homogeneous",
    "convert_affinematrix_to_homography",
    "angle_axis_to_rotation_matrix",
    "angle_axis_to_quaternion",
    "rotation_matrix_to_angle_axis",
    "rotation_matrix_to_quaternion",
    "quaternion_to_angle_axis",
    "quaternion_to_rotation_matrix",
    "quaternion_log_to_exp",
    "quaternion_exp_to_log",
    "denormalize_pixel_coordinates",
    "normalize_pixel_coordinates",
    "normalize_quaternion",
    "denormalize_pixel_coordinates3d",
    "normalize_pixel_coordinates3d",
]


def rad2deg(tensor: torch.Tensor) -> torch.Tensor:
    r"""Function that converts angles from radians to degrees.
    Args:
        tensor (torch.Tensor): Tensor of arbitrary shape.
    Returns:
        torch.Tensor: Tensor with same shape as input.
    Example:
        >>> input = kornia.pi * torch.rand(1, 3, 3)
        >>> output = kornia.rad2deg(input)
    """
    if not isinstance(tensor, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(tensor)))

    return 180. * tensor / pi.to(tensor.device).type(tensor.dtype)


def deg2rad(tensor: torch.Tensor) -> torch.Tensor:
    r"""Function that converts angles from degrees to radians.
    Args:
        tensor (torch.Tensor): Tensor of arbitrary shape.
    Returns:
        torch.Tensor: tensor with same shape as input.
    Examples::
        >>> input = 360. * torch.rand(1, 3, 3)
        >>> output = kornia.deg2rad(input)
    """
    if not isinstance(tensor, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(tensor)))

    return tensor * pi.to(tensor.device).type(tensor.dtype) / 180.


def convert_points_from_homogeneous(
        points: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    r"""Function that converts points from homogeneous to Euclidean space.
    Examples::
        >>> input = torch.rand(2, 4, 3)  # BxNx3
        >>> output = kornia.convert_points_from_homogeneous(input)  # BxNx2
    """
    if not isinstance(points, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(points)))

    if len(points.shape) < 2:
        raise ValueError("Input must be at least a 2D tensor. Got {}".format(
            points.shape))

    # we check for points at infinity
    z_vec: torch.Tensor = points[..., -1:]

    # set the results of division by zeror/near-zero to 1.0
    # follow the convention of opencv:
    # https://github.com/opencv/opencv/pull/14411/files
    mask: torch.Tensor = torch.abs(z_vec) > eps
    scale: torch.Tensor = torch.ones_like(z_vec).masked_scatter_(
        mask, torch.tensor(1.0).to(points.device) / z_vec[mask])

    return scale * points[..., :-1]


def convert_points_to_homogeneous(points: torch.Tensor) -> torch.Tensor:
    r"""Function that converts points from Euclidean to homogeneous space.
    Examples::
        >>> input = torch.rand(2, 4, 3)  # BxNx3
        >>> output = kornia.convert_points_to_homogeneous(input)  # BxNx4
    """
    if not isinstance(points, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(points)))
    if len(points.shape) < 2:
        raise ValueError("Input must be at least a 2D tensor. Got {}".format(
            points.shape))

    return torch.nn.functional.pad(points, [0, 1], "constant", 1.0)


def convert_affinematrix_to_homography(A: torch.Tensor) -> torch.Tensor:
    r"""Function that converts batch of affine matrices from [Bx2x3] to [Bx3x3].
    Examples::
        >>> input = torch.rand(2, 2, 3)  # Bx2x3
        >>> output = kornia.convert_affinematrix_to_homography(input)  # Bx3x3
    """
    if not isinstance(A, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(A)))
    if not (len(A.shape) == 3 and A.shape[-2:] == (2, 3)):
        raise ValueError("Input matrix must be a Bx2x3 tensor. Got {}"
                         .format(A.shape))
    H: torch.Tensor = torch.nn.functional.pad(A, [0, 0, 0, 1], "constant", value=0.)
    H[..., -1, -1] += 1.0
    return H


def angle_axis_to_rotation_matrix(angle_axis: torch.Tensor) -> torch.Tensor:
    r"""Convert 3d vector of axis-angle rotation to 3x3 rotation matrix
    Args:
        angle_axis (torch.Tensor): tensor of 3d vector of axis-angle rotations.
    Returns:
        torch.Tensor: tensor of 3x3 rotation matrices.
    Shape:
        - Input: :math:`(N, 3)`
        - Output: :math:`(N, 3, 3)`
    Example:
        >>> input = torch.rand(1, 3)  # Nx3
        >>> output = kornia.angle_axis_to_rotation_matrix(input)  # Nx3x3
    """
    if not isinstance(angle_axis, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(angle_axis)))

    if not angle_axis.shape[-1] == 3:
        raise ValueError(
            "Input size must be a (*, 3) tensor. Got {}".format(
                angle_axis.shape))

    def _compute_rotation_matrix(angle_axis, theta2, eps=1e-6):
        # We want to be careful to only evaluate the square root if the
        # norm of the angle_axis vector is greater than zero. Otherwise
        # we get a division by zero.
        k_one = 1.0
        theta = torch.sqrt(theta2)
        wxyz = angle_axis / (theta + eps)
        wx, wy, wz = torch.chunk(wxyz, 3, dim=1)
        cos_theta = torch.cos(theta)
        sin_theta = torch.sin(theta)

        r00 = cos_theta + wx * wx * (k_one - cos_theta)
        r10 = wz * sin_theta + wx * wy * (k_one - cos_theta)
        r20 = -wy * sin_theta + wx * wz * (k_one - cos_theta)
        r01 = wx * wy * (k_one - cos_theta) - wz * sin_theta
        r11 = cos_theta + wy * wy * (k_one - cos_theta)
        r21 = wx * sin_theta + wy * wz * (k_one - cos_theta)
        r02 = wy * sin_theta + wx * wz * (k_one - cos_theta)
        r12 = -wx * sin_theta + wy * wz * (k_one - cos_theta)
        r22 = cos_theta + wz * wz * (k_one - cos_theta)
        rotation_matrix = torch.cat(
            [r00, r01, r02, r10, r11, r12, r20, r21, r22], dim=1)
        return rotation_matrix.view(-1, 3, 3)

    def _compute_rotation_matrix_taylor(angle_axis):
        rx, ry, rz = torch.chunk(angle_axis, 3, dim=1)
        k_one = torch.ones_like(rx)
        rotation_matrix = torch.cat(
            [k_one, -rz, ry, rz, k_one, -rx, -ry, rx, k_one], dim=1)
        return rotation_matrix.view(-1, 3, 3)

    # stolen from ceres/rotation.h

    _angle_axis = torch.unsqueeze(angle_axis, dim=1)
    theta2 = torch.matmul(_angle_axis, _angle_axis.transpose(1, 2))
    theta2 = torch.squeeze(theta2, dim=1)

    # compute rotation matrices
    rotation_matrix_normal = _compute_rotation_matrix(angle_axis, theta2)
    rotation_matrix_taylor = _compute_rotation_matrix_taylor(angle_axis)

    # create mask to handle both cases
    eps = 1e-6
    mask = (theta2 > eps).view(-1, 1, 1).to(theta2.device)
    mask_pos = (mask).type_as(theta2)
    mask_neg = (mask == False).type_as(theta2)  # noqa

    # create output pose matrix
    batch_size = angle_axis.shape[0]
    rotation_matrix = torch.eye(3).to(angle_axis.device).type_as(angle_axis)
    rotation_matrix = rotation_matrix.view(1, 3, 3).repeat(batch_size, 1, 1)
    # fill output matrix with masked values
    rotation_matrix[..., :3, :3] = \
        mask_pos * rotation_matrix_normal + mask_neg * rotation_matrix_taylor
    return rotation_matrix  # Nx4x4


def rotation_matrix_to_angle_axis(
        rotation_matrix: torch.Tensor) -> torch.Tensor:
    r"""Convert 3x3 rotation matrix to Rodrigues vector.
    Args:
        rotation_matrix (torch.Tensor): rotation matrix.
    Returns:
        torch.Tensor: Rodrigues vector transformation.
    Shape:
        - Input: :math:`(N, 3, 3)`
        - Output: :math:`(N, 3)`
    Example:
        >>> input = torch.rand(2, 3, 3)  # Nx3x3
        >>> output = kornia.rotation_matrix_to_angle_axis(input)  # Nx3
    """
    if not isinstance(rotation_matrix, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(rotation_matrix)))

    if not rotation_matrix.shape[-2:] == (3, 3):
        raise ValueError(
            "Input size must be a (*, 3, 3) tensor. Got {}".format(
                rotation_matrix.shape))
    quaternion: torch.Tensor = rotation_matrix_to_quaternion(rotation_matrix)
    return quaternion_to_angle_axis(quaternion)


def rotation_matrix_to_quaternion(
        rotation_matrix: torch.Tensor,
        eps: float = 1e-8) -> torch.Tensor:
    r"""Convert 3x3 rotation matrix to 4d quaternion vector.
    The quaternion vector has components in (x, y, z, w) format.
    Args:
        rotation_matrix (torch.Tensor): the rotation matrix to convert.
        eps (float): small value to avoid zero division. Default: 1e-8.
    Return:
        torch.Tensor: the rotation in quaternion.
    Shape:
        - Input: :math:`(*, 3, 3)`
        - Output: :math:`(*, 4)`
    Example:
        >>> input = torch.rand(4, 3, 3)  # Nx3x3
        >>> output = kornia.rotation_matrix_to_quaternion(input)  # Nx4
    """
    if not isinstance(rotation_matrix, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(rotation_matrix)))

    if not rotation_matrix.shape[-2:] == (3, 3):
        raise ValueError(
            "Input size must be a (*, 3, 3) tensor. Got {}".format(
                rotation_matrix.shape))

    def safe_zero_division(numerator: torch.Tensor,
                           denominator: torch.Tensor) -> torch.Tensor:
        eps: float = torch.finfo(numerator.dtype).tiny  # type: ignore
        return numerator / torch.clamp(denominator, min=eps)

    rotation_matrix_vec: torch.Tensor = rotation_matrix.view(
        *rotation_matrix.shape[:-2], 9)

    m00, m01, m02, m10, m11, m12, m20, m21, m22 = torch.chunk(
        rotation_matrix_vec, chunks=9, dim=-1)

    trace: torch.Tensor = m00 + m11 + m22

    def trace_positive_cond():
        sq = torch.sqrt(trace + 1.0) * 2.  # sq = 4 * qw.
        qw = 0.25 * sq
        qx = safe_zero_division(m21 - m12, sq)
        qy = safe_zero_division(m02 - m20, sq)
        qz = safe_zero_division(m10 - m01, sq)
        return torch.cat([qx, qy, qz, qw], dim=-1)

    def cond_1():
        sq = torch.sqrt(1.0 + m00 - m11 - m22 + eps) * 2.  # sq = 4 * qx.
        qw = safe_zero_division(m21 - m12, sq)
        qx = 0.25 * sq
        qy = safe_zero_division(m01 + m10, sq)
        qz = safe_zero_division(m02 + m20, sq)
        return torch.cat([qx, qy, qz, qw], dim=-1)

    def cond_2():
        sq = torch.sqrt(1.0 + m11 - m00 - m22 + eps) * 2.  # sq = 4 * qy.
        qw = safe_zero_division(m02 - m20, sq)
        qx = safe_zero_division(m01 + m10, sq)
        qy = 0.25 * sq
        qz = safe_zero_division(m12 + m21, sq)
        return torch.cat([qx, qy, qz, qw], dim=-1)

    def cond_3():
        sq = torch.sqrt(1.0 + m22 - m00 - m11 + eps) * 2.  # sq = 4 * qz.
        qw = safe_zero_division(m10 - m01, sq)
        qx = safe_zero_division(m02 + m20, sq)
        qy = safe_zero_division(m12 + m21, sq)
        qz = 0.25 * sq
        return torch.cat([qx, qy, qz, qw], dim=-1)

    where_2 = torch.where(m11 > m22, cond_2(), cond_3())
    where_1 = torch.where(
        (m00 > m11) & (m00 > m22), cond_1(), where_2)

    quaternion: torch.Tensor = torch.where(
        trace > 0., trace_positive_cond(), where_1)
    return quaternion


def normalize_quaternion(quaternion: torch.Tensor,
                         eps: float = 1e-12) -> torch.Tensor:
    r"""Normalizes a quaternion.
    The quaternion should be in (x, y, z, w) format.
    Args:
        quaternion (torch.Tensor): a tensor containing a quaternion to be
          normalized. The tensor can be of shape :math:`(*, 4)`.
        eps (Optional[bool]): small value to avoid division by zero.
          Default: 1e-12.
    Return:
        torch.Tensor: the normalized quaternion of shape :math:`(*, 4)`.
    Example:
        >>> quaternion = torch.tensor([1., 0., 1., 0.])
        >>> kornia.normalize_quaternion(quaternion)
        tensor([0.7071, 0.0000, 0.7071, 0.0000])
    """
    if not isinstance(quaternion, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(quaternion)))

    if not quaternion.shape[-1] == 4:
        raise ValueError(
            "Input must be a tensor of shape (*, 4). Got {}".format(
                quaternion.shape))
    return F.normalize(quaternion, p=2, dim=-1, eps=eps)


# based on:
# https://github.com/matthew-brett/transforms3d/blob/8965c48401d9e8e66b6a8c37c65f2fc200a076fa/transforms3d/quaternions.py#L101
# https://github.com/tensorflow/graphics/blob/master/tensorflow_graphics/geometry/transformation/rotation_matrix_3d.py#L247

def quaternion_to_rotation_matrix(quaternion: torch.Tensor) -> torch.Tensor:
    r"""Converts a quaternion to a rotation matrix.
    The quaternion should be in (x, y, z, w) format.
    Args:
        quaternion (torch.Tensor): a tensor containing a quaternion to be
          converted. The tensor can be of shape :math:`(*, 4)`.
    Return:
        torch.Tensor: the rotation matrix of shape :math:`(*, 3, 3)`.
    Example:
        >>> quaternion = torch.tensor([0., 0., 1., 0.])
        >>> kornia.quaternion_to_rotation_matrix(quaternion)
        tensor([[[-1.,  0.,  0.],
                 [ 0., -1.,  0.],
                 [ 0.,  0.,  1.]]])
    """
    if not isinstance(quaternion, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(quaternion)))

    if not quaternion.shape[-1] == 4:
        raise ValueError(
            "Input must be a tensor of shape (*, 4). Got {}".format(
                quaternion.shape))
    # normalize the input quaternion
    quaternion_norm: torch.Tensor = normalize_quaternion(quaternion)

    # unpack the normalized quaternion components
    x, y, z, w = torch.chunk(quaternion_norm, chunks=4, dim=-1)

    # compute the actual conversion
    tx: torch.Tensor = 2.0 * x
    ty: torch.Tensor = 2.0 * y
    tz: torch.Tensor = 2.0 * z
    twx: torch.Tensor = tx * w
    twy: torch.Tensor = ty * w
    twz: torch.Tensor = tz * w
    txx: torch.Tensor = tx * x
    txy: torch.Tensor = ty * x
    txz: torch.Tensor = tz * x
    tyy: torch.Tensor = ty * y
    tyz: torch.Tensor = tz * y
    tzz: torch.Tensor = tz * z
    one: torch.Tensor = torch.tensor(1.)

    matrix: torch.Tensor = torch.stack([
        one - (tyy + tzz), txy - twz, txz + twy,
        txy + twz, one - (txx + tzz), tyz - twx,
        txz - twy, tyz + twx, one - (txx + tyy)
    ], dim=-1).view(-1, 3, 3)

    if len(quaternion.shape) == 1:
        matrix = torch.squeeze(matrix, dim=0)
    return matrix


def quaternion_to_angle_axis(quaternion: torch.Tensor) -> torch.Tensor:
    """Convert quaternion vector to angle axis of rotation.
    The quaternion should be in (x, y, z, w) format.
    Adapted from ceres C++ library: ceres-solver/include/ceres/rotation.h
    Args:
        quaternion (torch.Tensor): tensor with quaternions.
    Return:
        torch.Tensor: tensor with angle axis of rotation.
    Shape:
        - Input: :math:`(*, 4)` where `*` means, any number of dimensions
        - Output: :math:`(*, 3)`
    Example:
        >>> quaternion = torch.rand(2, 4)  # Nx4
        >>> angle_axis = kornia.quaternion_to_angle_axis(quaternion)  # Nx3
    """
    if not torch.is_tensor(quaternion):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(quaternion)))

    if not quaternion.shape[-1] == 4:
        raise ValueError(
            "Input must be a tensor of shape Nx4 or 4. Got {}".format(
                quaternion.shape))
    # unpack input and compute conversion
    q1: torch.Tensor = quaternion[..., 1]
    q2: torch.Tensor = quaternion[..., 2]
    q3: torch.Tensor = quaternion[..., 3]
    sin_squared_theta: torch.Tensor = q1 * q1 + q2 * q2 + q3 * q3

    sin_theta: torch.Tensor = torch.sqrt(sin_squared_theta)
    cos_theta: torch.Tensor = quaternion[..., 0]
    two_theta: torch.Tensor = 2.0 * torch.where(
        cos_theta < 0.0, torch.atan2(-sin_theta, -cos_theta),
        torch.atan2(sin_theta, cos_theta))

    k_pos: torch.Tensor = two_theta / sin_theta
    k_neg: torch.Tensor = 2.0 * torch.ones_like(sin_theta)
    k: torch.Tensor = torch.where(sin_squared_theta > 0.0, k_pos, k_neg)

    angle_axis: torch.Tensor = torch.zeros_like(quaternion)[..., :3]
    angle_axis[..., 0] += q1 * k
    angle_axis[..., 1] += q2 * k
    angle_axis[..., 2] += q3 * k
    return angle_axis


def quaternion_log_to_exp(quaternion: torch.Tensor,
                          eps: float = 1e-8) -> torch.Tensor:
    r"""Applies exponential map to log quaternion.
    The quaternion should be in (x, y, z, w) format.
    Args:
        quaternion (torch.Tensor): a tensor containing a quaternion to be
          converted. The tensor can be of shape :math:`(*, 3)`.
    Return:
        torch.Tensor: the quaternion exponential map of shape :math:`(*, 4)`.
    Example:
        >>> quaternion = torch.tensor([0., 0., 0.])
        >>> kornia.quaternion_log_to_exp(quaternion)
        tensor([0., 0., 0., 1.])
    """
    if not isinstance(quaternion, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(quaternion)))

    if not quaternion.shape[-1] == 3:
        raise ValueError(
            "Input must be a tensor of shape (*, 3). Got {}".format(
                quaternion.shape))
    # compute quaternion norm
    norm_q: torch.Tensor = torch.norm(
        quaternion, p=2, dim=-1, keepdim=True).clamp(min=eps)

    # compute scalar and vector
    quaternion_vector: torch.Tensor = quaternion * torch.sin(norm_q) / norm_q
    quaternion_scalar: torch.Tensor = torch.cos(norm_q)

    # compose quaternion and return
    quaternion_exp: torch.Tensor = torch.cat(
        [quaternion_vector, quaternion_scalar], dim=-1)
    return quaternion_exp


def quaternion_exp_to_log(quaternion: torch.Tensor,
                          eps: float = 1e-8) -> torch.Tensor:
    r"""Applies the log map to a quaternion.
    The quaternion should be in (x, y, z, w) format.
    Args:
        quaternion (torch.Tensor): a tensor containing a quaternion to be
          converted. The tensor can be of shape :math:`(*, 4)`.
    Return:
        torch.Tensor: the quaternion log map of shape :math:`(*, 3)`.
    Example:
        >>> quaternion = torch.tensor([0., 0., 0., 1.])
        >>> kornia.quaternion_exp_to_log(quaternion)
        tensor([0., 0., 0.])
    """
    if not isinstance(quaternion, torch.Tensor):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(quaternion)))

    if not quaternion.shape[-1] == 4:
        raise ValueError(
            "Input must be a tensor of shape (*, 4). Got {}".format(
                quaternion.shape))
    # unpack quaternion vector and scalar
    quaternion_vector: torch.Tensor = quaternion[..., 0:3]
    quaternion_scalar: torch.Tensor = quaternion[..., 3:4]

    # compute quaternion norm
    norm_q: torch.Tensor = torch.norm(
        quaternion_vector, p=2, dim=-1, keepdim=True).clamp(min=eps)

    # apply log map
    quaternion_log: torch.Tensor = quaternion_vector * torch.acos(
        torch.clamp(quaternion_scalar, min=-1.0, max=1.0)) / norm_q
    return quaternion_log


# based on:
# https://github.com/facebookresearch/QuaterNet/blob/master/common/quaternion.py#L138


def angle_axis_to_quaternion(angle_axis: torch.Tensor) -> torch.Tensor:
    r"""Convert an angle axis to a quaternion.
    The quaternion vector has components in (x, y, z, w) format.
    Adapted from ceres C++ library: ceres-solver/include/ceres/rotation.h
    Args:
        angle_axis (torch.Tensor): tensor with angle axis.
    Return:
        torch.Tensor: tensor with quaternion.
    Shape:
        - Input: :math:`(*, 3)` where `*` means, any number of dimensions
        - Output: :math:`(*, 4)`
    Example:
        >>> angle_axis = torch.rand(2, 4)  # Nx4
        >>> quaternion = kornia.angle_axis_to_quaternion(angle_axis)  # Nx3
    """
    if not torch.is_tensor(angle_axis):
        raise TypeError("Input type is not a torch.Tensor. Got {}".format(
            type(angle_axis)))

    if not angle_axis.shape[-1] == 3:
        raise ValueError(
            "Input must be a tensor of shape Nx3 or 3. Got {}".format(
                angle_axis.shape))
    # unpack input and compute conversion
    a0: torch.Tensor = angle_axis[..., 0:1]
    a1: torch.Tensor = angle_axis[..., 1:2]
    a2: torch.Tensor = angle_axis[..., 2:3]
    theta_squared: torch.Tensor = a0 * a0 + a1 * a1 + a2 * a2

    theta: torch.Tensor = torch.sqrt(theta_squared)
    half_theta: torch.Tensor = theta * 0.5

    mask: torch.Tensor = theta_squared > 0.0
    ones: torch.Tensor = torch.ones_like(half_theta)

    k_neg: torch.Tensor = 0.5 * ones
    k_pos: torch.Tensor = torch.sin(half_theta) / theta
    k: torch.Tensor = torch.where(mask, k_pos, k_neg)
    w: torch.Tensor = torch.where(mask, torch.cos(half_theta), ones)

    quaternion: torch.Tensor = torch.zeros_like(angle_axis)
    quaternion[..., 0:1] += a0 * k
    quaternion[..., 1:2] += a1 * k
    quaternion[..., 2:3] += a2 * k
    return torch.cat([w, quaternion], dim=-1)


# based on:
# https://github.com/ClementPinard/SfmLearner-Pytorch/blob/master/inverse_warp.py#L65-L71

def normalize_pixel_coordinates(
        pixel_coordinates: torch.Tensor,
        height: int,
        width: int,
        eps: float = 1e-8) -> torch.Tensor:
    r"""Normalize pixel coordinates between -1 and 1.
    Normalized, -1 if on extreme left, 1 if on extreme right (x = w-1).
    Args:
        pixel_coordinates (torch.Tensor): the grid with pixel coordinates.
          Shape can be :math:`(*, 2)`.
        width (int): the maximum width in the x-axis.
        height (int): the maximum height in the y-axis.
        eps (float): safe division by zero. (default 1e-8).
    Return:
        torch.Tensor: the normalized pixel coordinates.
    """
    if pixel_coordinates.shape[-1] != 2:
        raise ValueError("Input pixel_coordinates must be of shape (*, 2). "
                         "Got {}".format(pixel_coordinates.shape))
    # compute normalization factor
    hw: torch.Tensor = torch.stack([
        torch.tensor(width), torch.tensor(height)
    ]).to(pixel_coordinates.device).to(pixel_coordinates.dtype)

    factor: torch.Tensor = torch.tensor(2.) / (hw - 1).clamp(eps)

    return factor * pixel_coordinates - 1


def denormalize_pixel_coordinates(
        pixel_coordinates: torch.Tensor,
        height: int,
        width: int,
        eps: float = 1e-8) -> torch.Tensor:
    r"""Denormalize pixel coordinates.
    The input is assumed to be -1 if on extreme left, 1 if on
    extreme right (x = w-1).
    Args:
        pixel_coordinates (torch.Tensor): the normalized grid coordinates.
          Shape can be :math:`(*, 2)`.
        width (int): the maximum width in the x-axis.
        height (int): the maximum height in the y-axis.
        eps (float): safe division by zero. (default 1e-8).
    Return:
        torch.Tensor: the denormalized pixel coordinates.
    """
    if pixel_coordinates.shape[-1] != 2:
        raise ValueError("Input pixel_coordinates must be of shape (*, 2). "
                         "Got {}".format(pixel_coordinates.shape))
    # compute normalization factor
    hw: torch.Tensor = torch.stack([
        torch.tensor(width), torch.tensor(height)
    ]).to(pixel_coordinates.device).to(pixel_coordinates.dtype)

    factor: torch.Tensor = torch.tensor(2.) / (hw - 1).clamp(eps)

    return torch.tensor(1.) / factor * (pixel_coordinates + 1)


def normalize_pixel_coordinates3d(
        pixel_coordinates: torch.Tensor,
        depth: int,
        height: int,
        width: int,
        eps: float = 1e-8) -> torch.Tensor:
    r"""Normalize pixel coordinates between -1 and 1.
    Normalized, -1 if on extreme left, 1 if on extreme right (x = w-1).
    Args:
        pixel_coordinates (torch.Tensor): the grid with pixel coordinates.
          Shape can be :math:`(*, 3)`.
        depth (int): the maximum depth in the z-axis.
        height (int): the maximum height in the y-axis.
        width (int): the maximum width in the x-axis.
        eps (float): safe division by zero. (default 1e-8).
    Return:
        torch.Tensor: the normalized pixel coordinates.
    """
    if pixel_coordinates.shape[-1] != 3:
        raise ValueError("Input pixel_coordinates must be of shape (*, 3). "
                         "Got {}".format(pixel_coordinates.shape))
    # compute normalization factor
    dhw: torch.Tensor = torch.stack([
        torch.tensor(depth), torch.tensor(width), torch.tensor(height)
    ]).to(pixel_coordinates.device).to(pixel_coordinates.dtype)

    factor: torch.Tensor = torch.tensor(2.) / (dhw - 1).clamp(eps)

    return factor * pixel_coordinates - 1


def denormalize_pixel_coordinates3d(
        pixel_coordinates: torch.Tensor,
        depth: int,
        height: int,
        width: int,
        eps: float = 1e-8) -> torch.Tensor:
    r"""Denormalize pixel coordinates.
    The input is assumed to be -1 if on extreme left, 1 if on
    extreme right (x = w-1).
    Args:
        pixel_coordinates (torch.Tensor): the normalized grid coordinates.
          Shape can be :math:`(*, 3)`.
        depth (int): the maximum depth in the x-axis.
        height (int): the maximum height in the y-axis.
        width (int): the maximum width in the x-axis.
        eps (float): safe division by zero. (default 1e-8).
    Return:
        torch.Tensor: the denormalized pixel coordinates.
    """
    if pixel_coordinates.shape[-1] != 3:
        raise ValueError("Input pixel_coordinates must be of shape (*, 3). "
                         "Got {}".format(pixel_coordinates.shape))
    # compute normalization factor
    dhw: torch.Tensor = torch.stack([
        torch.tensor(depth), torch.tensor(width), torch.tensor(height)
    ]).to(pixel_coordinates.device).to(pixel_coordinates.dtype)

    factor: torch.Tensor = torch.tensor(2.) / (dhw - 1).clamp(eps)

    return torch.tensor(1.) / factor * (pixel_coordinates + 1)
