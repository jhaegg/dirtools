# -*- encoding: utf-8 -*-
import re
import fnmatch
import logging
import os
import hashlib
import functools

from globster import Globster
# TODO se decider entre `path' et `filename', `filepath' and `directory'
# TODO une option pour exclude ['.hg', '.svn', 'git']
# TODO gerer les ecludes dans Dir.subdirs =>  topdown=True, pareils que Dir.files
#      => http://stackoverflow.com/questions/5141437/filtering-os-walk-dirs-and-files

# TODO? faire des raccourcis, genre dirtools.listsubdir => Dir(path).subdirs

log = logging.getLogger("dirtools")


def load_patterns(exclude_file=".exclude"):
    """ Load patterns to exclude file from `exclude_file',
    and return a list of pattern.

    :type exclude_file: str
    :param exclude_file: File containing exclude patterns

    :rtype: list
    :return: List a patterns

    """
    return filter(None, open(exclude_file).read().split("\n"))


def filehash(filepath, blocksize=4096):
    """ Return the hash for the file `filepath', processing the file
    by chunk of `blocksize'. """
    sha = hashlib.sha256()
    with open(filepath, 'rb') as fp:
        while 1:
            data = fp.read(blocksize)
            if data:
                sha.update(data)
            else:
                break
    return sha.hexdigest()


def hashdir(dirname):
    """ Compute sha256 hash for `dirname'. """
    shadir = hashlib.sha256()
    for root, dirs, files in os.walk(dirname):
        for fpath in [os.path.join(root, f) for f in files]:
            try:
                #size = os.path.getsize(fpath)
                sha = filehash(fpath)
                #name = os.path.relpath(fpath, dirname)
                shadir.update(sha)
            except (IOError, OSError):
                pass
        return shadir.hexdigest()


class Dir(object):
    def __init__(self, directory=".", exclude_file=".exclude", excludes=['.git/', '.hg/', '.svn/']):
        self.directory = directory
        self.path = os.path.abspath(directory)
        self.exclude_file = os.path.join(self.path, exclude_file)
        self.patterns = excludes
        if os.path.isfile(self.exclude_file):
            self.patterns.extend(load_patterns(self.exclude_file))
        self.globster = Globster(self.patterns)

    def is_excluded(self, path):
        """ Return True if `path' should be excluded
        given patterns in the `exclude_file'. """
        match = self.globster.match(self.relpath(path))
        if match:
            log.debug("{0} matched {1} for exclusion".format(path, match))
            return True
        return False

    def walk(self):
        """ Walk the directory like os.path
        (yields a 3-tuple (dirpath, dirnames, filenames)
        except it exclude all files/directories on the fly.
        """
        for root, dirs, files in os.walk(self.path, topdown=True):
            ndirs = []
            # First we exclude directories
            for d in list(dirs):
                if self.is_excluded(os.path.join(root, d)):
                    dirs.remove(d)
                else:
                    ndirs.append(d)

            nfiles = []
            for fpath in (os.path.join(root, f) for f in files):
                if not self.is_excluded(fpath):
                    nfiles.append(os.path.relpath(fpath, root))

            yield root, ndirs, nfiles

    @property
    def files(self):
        """ Generator for all the files not excluded recursively. """
        for root, dirs, files in self.walk():
            for f in files:
                yield self.relpath(os.path.join(root, f))

    @property
    def hash(self):
        """ Hash for the entire directory recursively. """
        shadir = hashlib.sha256()
        for f in self.files:
            try:
                shadir.update(filehash(f))
            except (IOError, OSError):
                pass
        return shadir.hexdigest()

    @property
    def subdirs(self):
        """ List of all subdirs. """
        for root, dirs, files in self.walk():
            for d in dirs:
                yield self.relpath(os.path.join(root, d))

    def find_project(self, file_identifier=".project"):
        """ Search all directory recursively for subdirs
        with `file_identifier' in it.

        :type file_identifier: str
        :param file_identifier: File identier, .project by default.

        :rtype: list
        :return: The list of subdirs with a `file_identifier' in it.

        """
        for d in self.subdirs:
            if os.path.isfile(os.path.join(d, file_identifier)):
                yield d

    def relpath(self, path):
        """ Return a relative filepath to path from Dir path. """
        return os.path.relpath(path, start=self.path)