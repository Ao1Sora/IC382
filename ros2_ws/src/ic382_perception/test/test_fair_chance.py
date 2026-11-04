import unittest
from ic382_perception.fair_chance import (
    STATUS_CONFIRMED,
    STATUS_NEW,
    STATUS_OCCUPIED,
    STATUS_OWNER_RETURNED,
    DetectionRecord,
    Item,
    associate,
    iou_xywh,
    merge_across_views,
    new_items,
    validate_round2,
)


def record(class_code="C", confidence=0.9, position=(0.0, 0.0, 1.0),
           base=(0.0, 0.0, 1.0), point="T01-A"):
    return DetectionRecord(
        class_code=class_code,
        class_name="disposables" if class_code == "C" else "ic_material",
        confidence=confidence,
        bbox=(100.0, 100.0, 40.0, 40.0),
        position_m=position,
        base_position_m=base,
        point_id=point,
    )


def item(item_id=1, class_code="C", position=(0.0, 0.0, 1.0)):
    return Item(
        item_id=item_id,
        class_code=class_code,
        class_name="disposables" if class_code == "C" else "ic_material",
        confidence=0.9,
        bbox=(100.0, 100.0, 40.0, 40.0),
        position_m=position,
        first_point_id="T01-A",
    )


class FairChanceTests(unittest.TestCase):
    def test_iou(self):
        self.assertAlmostEqual(iou_xywh((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)
        self.assertEqual(iou_xywh((0, 0, 10, 10), (100, 100, 10, 10)), 0.0)

    def test_associate_by_position(self):
        matches = associate([item(1)], [record(position=(0.05, 0.0, 1.0))])
        self.assertIn(1, matches)

    def test_associate_requires_same_class(self):
        matches = associate([item(1, class_code="A")], [record(class_code="C")])
        self.assertNotIn(1, matches)

    def test_merge_across_views_keeps_one_item(self):
        items, next_id = merge_across_views([], [record(point="T01-A")], 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(next_id, 2)
        items, next_id = merge_across_views(items, [record(point="T01-B")], next_id)
        self.assertEqual(len(items), 1)
        self.assertEqual(next_id, 2)

    def test_merge_creates_new_item_for_new_position(self):
        items, next_id = merge_across_views([], [record()], 1)
        items, next_id = merge_across_views(
            items, [record(position=(5.0, 0.0, 1.0))], next_id)
        self.assertEqual(len(items), 2)
        self.assertEqual(next_id, 3)

    def test_validate_confirmed_and_owner_returned(self):
        items = [item(1), item(2)]
        matches = {1: record()}
        results = validate_round2(items, matches, occupied=False)
        by_id = {result.item_id: result for result in results}
        self.assertEqual(by_id[1].status, STATUS_CONFIRMED)
        self.assertEqual(by_id[1].action_taken, "TAGGED_CLASS_C")
        self.assertEqual(by_id[2].status, STATUS_OWNER_RETURNED)
        self.assertEqual(by_id[2].action_taken, "NO_TAG_OWNER_RETURNED")

    def test_validate_occupied_cancels_every_item(self):
        results = validate_round2([item(1)], {1: record()}, occupied=True)
        self.assertEqual(results[0].status, STATUS_OCCUPIED)
        self.assertEqual(results[0].action_taken, "NO_TAG_DESK_OCCUPIED")

    def test_validate_tagging_disabled(self):
        results = validate_round2([item(1)], {1: record()}, tagging_enabled=False)
        self.assertEqual(results[0].status, STATUS_CONFIRMED)
        self.assertEqual(results[0].action_taken, "NO_TAG_UNKNOWN")

    def test_new_items(self):
        results, next_id = new_items([record()], 5)
        self.assertEqual(results[0].status, STATUS_NEW)
        self.assertEqual(next_id, 6)


if __name__ == "__main__":
    unittest.main()
