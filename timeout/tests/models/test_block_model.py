"""
test_block_model.py - Defines BlockModelTest for testing the Block model's functionality, including creation, string representation,
uniqueness constraints, directional blocking behavior, and cascade deletion when a user is deleted.
"""


from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from timeout.models import Block

User = get_user_model()


class BlockModelTest(TestCase):
    """Tests for the Block model, which represents user blocks in the social features of the application."""
    def setUp(self):
        """Set up test users for block tests."""
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")

    def test_create_block(self):
        """Test creating a block."""
        block = Block.objects.create(blocker=self.u1, blocked=self.u2)
        self.assertEqual(block.blocker, self.u1)
        self.assertEqual(block.blocked, self.u2)

    def test_block_str(self):
        """Test the string representation of a block."""
        block = Block.objects.create(blocker=self.u1, blocked=self.u2)
        self.assertIn("u1", str(block))
        self.assertIn("u2", str(block))

    def test_block_unique_together(self):
        """Test that a user cannot block the same user twice."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        with self.assertRaises(IntegrityError):
            Block.objects.create(blocker=self.u1, blocked=self.u2)

    def test_block_is_directional(self):
        """Test that blocking is directional."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        # reverse direction should be allowed
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        self.assertEqual(Block.objects.count(), 2)

    def test_block_deleted_on_user_delete(self):
        """Test that blocks are deleted when a user is deleted."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        self.u1.delete()
        self.assertEqual(Block.objects.count(), 0)