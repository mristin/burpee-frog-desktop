"""Crop the individual sprites from the sprite sheet."""

import argparse
import os
import pathlib
import sys

import PIL
import PIL.Image


def main() -> int:
    """Execute the main routine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    this_path = pathlib.Path(os.path.realpath(__file__))
    images_dir = this_path.parent.parent / "burpeefrog/media/images"
    sheet_path = images_dir / "frog.png"

    image = PIL.Image.open(
        str(this_path.parent.parent / "burpeefrog/media/images/frog.png")
    )
    png_info = dict()
    if image.mode not in ['RGB', 'RGBA']:
        image = image.convert('RGBA')
        png_info = image.info

    image_w, image_h = image.size
    sprite_w = int(image_w / 4)
    sprite_h = image_h

    for i in range(4):
        xmin = i * sprite_w
        xmax = i * sprite_w + sprite_w

        ymin = 0
        ymax = sprite_h

        cropped = image.crop((xmin, ymin, xmax, ymax))
        cropped = cropped.resize((50, 100))

        cropped.save(str(images_dir / f"frog{i}.png"), **png_info)

    return 0




    return 0


if __name__ == "__main__":
    sys.exit(main())
