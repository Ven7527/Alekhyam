Installation
============

Requirements
------------

- Python 3.9 or newer
- PySide6 ≥ 6.5
- pandas ≥ 2.0
- matplotlib ≥ 3.7
- scienceplots ≥ 2.1
- qtawesome ≥ 1.3

Install from PyPI
-----------------

.. code-block:: bash

   pip install alekhyam

Launch
------

.. code-block:: bash

   alekhyam

**Linux** — a desktop entry is registered automatically on first launch so
Alekhyam appears in your application menu.

**Windows** — run the following once after installing to create a Start Menu
shortcut (also runs automatically on first launch):

.. code-block:: bash

   alekhyam-register

Troubleshooting
---------------

**Windows:** ``ImportError: DLL load failed while importing QtGui``

This happens when Alekhyam is installed into a Conda/Anaconda environment whose
**base env** already ships its own Qt5 (pulled in by ``pyqt``, ``qt``, or a
dependency like Jupyter/Spyder).  Those Qt5 DLLs collide with PySide6's
bundled Qt6 DLLs, causing the load to fail.

Fix — install into a fresh, isolated environment instead of the Anaconda
base environment:

.. code-block:: bash

   conda create -n alekhyam python=3.11
   conda activate alekhyam
   pip install alekhyam
   alekhyam

If you need to keep using an existing environment, remove the conflicting
Qt packages first, then reinstall PySide6:

.. code-block:: bash

   conda remove pyqt qt qt-main --force
   pip install --force-reinstall pyside6

Building the documentation
--------------------------

Install the documentation dependencies and run Sphinx:

.. code-block:: bash

   pip install sphinx furo
   cd docs
   make html

The output lands in ``docs/_build/html/index.html``.
