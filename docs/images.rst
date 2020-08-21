:mod:`porcupine.images` --- Load images that come with Porcupine
================================================================

.. module:: porcupine.images

This is a tiny Python module for loading images from :source:`porcupine/images`.
Click that link to view available images on GitHub.

Prefer ``logo-200x200`` over ``logo`` if you need to load an image when
Porcupine starts. ``images.get('logo')`` seems to take about 225 milliseconds on
this system while ``images.get('logo-200x200')`` returns in about 5
milliseconds.

.. data:: images_dir

    This is the directory containing the images.
    You can do ``images_dir / 'logo.gif'``, for example.

.. autofunction:: get
