#!/usr/bin/env python3
"""v7マイグレーション実行スクリプト"""
from database import migrate_v7_card_groups, update_card_numbers

print("Running migration v7...")
migrate_v7_card_groups()

print("Updating card numbers...")
update_card_numbers()

print("Done!")
