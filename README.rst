What the H*** is AFNI?
----------------------

.. image:: https://travis-ci.org/afni/afni.svg?branch=master
    :target: https://travis-ci.org/afni/afni
    
.. image:: https://circleci.com/gh/afni/afni/tree/master.svg?style=shield
    :target: https://circleci.com/gh/afni/afni/tree/master

.. image:: https://codecov.io/gh/afni/afni/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/afni/afni


AFNI (Analysis of Functional NeuroImages) is a suite of programs for looking at and analyzing MRI brain
images.  It comprises a suite of C, Python, R programs and shell scripts primarily developed for the 
analysis and display of multiple MRI modalities: anatomical, functional MRI (FMRI) and diffusion 
weighted (DW) data.  It has graphical displays for both slice-wise and surface-based viewing.
  
| Please visit these websites for more information:
| https://afni.nimh.nih.gov/
| https://afni.nimh.nih.gov/pub/dist/doc/htmldoc/ 


| For questions on using AFNI programs, our Message Board is here:  
| https://afni.nimh.nih.gov/afni/community/board/list.php?1 .


AFNI code directory
-------------------

Currently top directory contains three sub-directories

doc/
    documentation for AFNI (though this is outdated; current doc content resides in its own git tree here: https://github.com/afni/afni_doc)
src/
    source code for AFNI
tests/
    tests for AFNI

Relevant git-ology for AFNI
---------------------------

First time stuff
~~~~~~~~~~~~~~~~

1. Make yourself known to git-land::

    git config --global user.name   "Fred Mertz"
    git config --global user.email  mertzf@bargle.argle
    git config --global core.editor vim

2. Create a copy of the repository on your machine::

    git clone https://github.com/afni/afni.git

Stuff to do as needed
~~~~~~~~~~~~~~~~~~~~~

- Getting updates from the repository::

    git pull origin master

- Seeing what changes you have made locally::

    git status

- To commit some files to your LOCAL repository (preferred)::

    git commit -m "PLEASE comment"   FILE1 FILE2 ...

- To commit all tracked files with changes (locally)::

    git commit -a -m "PLEASE try to put a comment here"

- If you have new files to add into the repository;
  **PLEASE PLEASE PLEASE, be careful with wildcards!!!**
  The main thing is to avoid adding very large files (such as binaries)
  by mistake!::

    git add -f FILE1 FILE2 ...

- Sending the local updates to the master (github.com) repository

    git push origin master


Compilation of AFNI
-------------------

In src/, you need to choose one of the Makefile.* files that is closest
to your system, and cp it to be named Makefile.  Makefile is set up to
install into the INSTALLDIR location, defined in that file -- you should
probably change that to be appropriate for your use.

If you are using Mac OS X, choose one of the Makefile.macosx_* files.

  For later versions of Mac OS X, Apple's C compiler does not support
  OpenMP, so we recommend downloading and installing a version of gcc
  from http://hpc.sourceforge.net/ or purchasing a commercial C compiler
  (e.g., Intel's icc) that does support OpenMP.  Several important
  programs in the AFNI suite are parallelized via OpenMP, and will run
  much faster if compiled appropriately.

If you are using Linux, try Makefile.linux_openmp_64 first.

To make and install everything do::

    make vastness

The command::

    make cleanest

will remove all the *.o files, etc.
