# -*- coding: utf-8; -*-
import os
from os.path import join, abspath
from unittest import TestCase
from shutil import copytree, rmtree
from tempfile import mkdtemp

from git import Repo

from sipa.utils.git_utils import init_repo, update_repo


GIT_FIXTURES_DIR = abspath("./tests/git_data/")
EXAMPLE_CONTENT_DIR_NAME = "content"
EXAMPLE_CONTENT_BARE_DIR_NAME = "content.git"
EXAMPLE_UPDATED_CONTENT_DIR_NAME = "content_updated"
EXAMPLE_UPDATED_CONTENT_BARE_DIR_NAME = "content_updated.git"


class GitInitializedTestBase(TestCase):
    def setUp(self):
        self.remote_url = join(GIT_FIXTURES_DIR, EXAMPLE_CONTENT_BARE_DIR_NAME)
        self.original_content_dir = join(GIT_FIXTURES_DIR, EXAMPLE_CONTENT_DIR_NAME)
        self.original_repo = Repo(self.original_content_dir)

        self.content_dir = mkdtemp()
        init_repo(repo_dir=self.content_dir, repo_url=self.remote_url)
        self.repo = Repo(self.content_dir)

    def tearDown(self):
        rmtree(self.content_dir)


class GitUpdateTestBase(TestCase):
    def setUp(self):
        super().setUp()
        self.tmp_dir = mkdtemp()
        self.content_dir = join(self.tmp_dir, 'content')

        self.original_content_dir = join(GIT_FIXTURES_DIR,
                                         EXAMPLE_UPDATED_CONTENT_DIR_NAME)

        src = join(GIT_FIXTURES_DIR, EXAMPLE_CONTENT_DIR_NAME)
        copytree(src, self.content_dir)

        new_url = join(GIT_FIXTURES_DIR, EXAMPLE_UPDATED_CONTENT_BARE_DIR_NAME)
        Repo(self.content_dir).git.remote('set-url', 'origin', new_url)
        update_repo(self.content_dir)

        self.original_repo = Repo(self.original_content_dir)
        self.repo = Repo(self.content_dir)

    def tearDown(self):
        super().tearDown()
        rmtree(self.tmp_dir)


class ContentStatusTesterMixin:
    def setUp(self):
        super().setUp()
        print("Running for class", type(self))

    def test_content_files_correct(self):
        self.assertEqual({*os.listdir(self.content_dir)},
                         {*os.listdir(self.original_content_dir)})

    def test_content_commit_correct(self):
        self.assertEqual(self.original_repo.commit().hexsha,
                         self.repo.commit().hexsha)

    def test_content_git_head_correct(self):
        self.assertEqual(self.original_repo.head.ref,
                         self.repo.head.ref)


class ContentInitTestCase(ContentStatusTesterMixin, GitInitializedTestBase):
    pass


class ContentUpdateTestCase(ContentStatusTesterMixin, GitUpdateTestBase):
    pass
