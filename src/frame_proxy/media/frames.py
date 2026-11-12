from __future__ import annotations

from dataclasses import dataclass

from frame_proxy.domain.errors import ErrorCode, MediaValidationError
from frame_proxy.media.avi import AviDescriptor


@dataclass(frozen=True, slots=True)
class Frame:
    index: int
    width: int
    height: int
    rgb: bytes


def decode_frame_at(
    buffer: bytes,
    descriptor: AviDescriptor,
    frame_index: int,
) -> Frame:
    if frame_index < 0 or frame_index >= descriptor.frame_count:
        raise MediaValidationError(
            "frame index is outside the clip",
            code=ErrorCode.MEDIA_BOUNDS,
            details={"frame_index": frame_index},
        )
    offset = descriptor.frame_offsets[frame_index]
    end = offset + descriptor.frame_payload_size
    if end > len(buffer):
        raise MediaValidationError(
            "frame payload is truncated",
            code=ErrorCode.FRAME_DECODE,
        )

    plane = memoryview(buffer)[offset:end]
    pixel_width = descriptor.width * 3
    packed_size = pixel_width * descriptor.height
    padded_size = descriptor.row_stride * descriptor.height
    if len(plane) < packed_size or len(plane) < padded_size:
        raise MediaValidationError(
            "frame has insufficient packed pixels",
            code=ErrorCode.FRAME_DECODE,
        )
    rows = _unpack_bgr_plane(
        plane,
        pixel_width=pixel_width,
        row_stride=descriptor.row_stride,
        height=descriptor.height,
        top_down=descriptor.top_down,
    )
    return Frame(
        index=frame_index,
        width=descriptor.width,
        height=descriptor.height,
        rgb=b"".join(rows),
    )



def _unpack_bgr_plane(
    plane: memoryview,
    *,
    pixel_width: int,
    row_stride: int,
    height: int,
    top_down: bool,
) -> tuple[bytes, ...]:
    converted_rows: list[bytes] = []
    for display_row in range(height):
        storage_row = display_row if top_down else height - 1 - display_row
        start = storage_row * row_stride
        finish = start + pixel_width
        source = plane[start:finish]
        if len(source) != pixel_width:
            raise MediaValidationError(
                "packed frame row is truncated",
                code=ErrorCode.FRAME_DECODE,
            )
        target = bytearray(pixel_width)
        target[0::3] = source[2::3]
        target[1::3] = source[1::3]
        target[2::3] = source[0::3]
        converted_rows.append(bytes(target))
    return tuple(converted_rows)
