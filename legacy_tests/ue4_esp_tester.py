#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أداة اختبار كشف ESP لمحرك UE4
تقرأ من الذاكرة وتكتشف محاولات استخدام ESP (عرض موقع اللاعبين)
"""

import ctypes
import struct
import math
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import win32process
import win32api
import psutil

# ============= Structures =============

@dataclass
class FVector:
    X: float
    Y: float
    Z: float

    def distance_to(self, other: 'FVector') -> float:
        dx = self.X - other.X
        dy = self.Y - other.Y
        dz = self.Z - other.Z
        return math.sqrt(dx**2 + dy**2 + dz**2)

    def __repr__(self):
        return f"FVector({self.X:.2f}, {self.Y:.2f}, {self.Z:.2f})"


@dataclass
class FMatrix:
    """مصفوفة 4x4 لتحويل الإحداثيات"""
    M: List[List[float]]

    @staticmethod
    def identity():
        return FMatrix([[1 if i == j else 0 for j in range(4)] for i in range(4)])

    def transform_point(self, p: FVector) -> FVector:
        """تحويل نقطة من World Space إلى Screen Space"""
        x = (self.M[0][0] * p.X + self.M[0][1] * p.Y +
             self.M[0][2] * p.Z + self.M[0][3])
        y = (self.M[1][0] * p.X + self.M[1][1] * p.Y +
             self.M[1][2] * p.Z + self.M[1][3])
        z = (self.M[2][0] * p.X + self.M[2][1] * p.Y +
             self.M[2][2] * p.Z + self.M[2][3])
        w = (self.M[3][0] * p.X + self.M[3][1] * p.Y +
             self.M[3][2] * p.Z + self.M[3][3])

        if w != 0:
            x /= w
            y /= w
            z /= w

        return FVector(x, y, z)


@dataclass
class ESPTarget:
    name: str
    world_position: FVector
    screen_position: FVector
    distance: float
    actor_id: int
    is_visible: bool
    is_detected: bool = False
    detection_method: str = ""


class DetectionMethod(Enum):
    """طرق الكشف المختلفة"""
    SUDDEN_AIM_CHANGE = "تغير حاد في التوجه"
    DISTANCE_ANOMALY = "شذوذ في المسافة"
    IMPOSSIBLE_VISIBILITY = "رؤية مستحيلة"
    ANGLE_ANOMALY = "شذوذ في الزاوية"
    PLAYER_BEHAVIOR = "سلوك اللاعب غير طبيعي"
    NONE = "لم يتم الكشف"


# ============= Memory Reader =============

class UE4MemoryReader:
    """قارئ الذاكرة لـ UE4"""

    def __init__(self, process_handle):
        self.process_handle = process_handle
        self.process_id = None

    def read_memory(self, address: int, size: int) -> bytes:
        """قراءة بيانات من الذاكرة"""
        try:
            data = ctypes.string_at(address, size)
            return data
        except Exception as e:
            print(f"خطأ في قراءة الذاكرة من {hex(address)}: {e}")
            return b''

    def read_float(self, address: int) -> float:
        """قراءة float من الذاكرة"""
        data = self.read_memory(address, 4)
        if len(data) == 4:
            return struct.unpack('<f', data)[0]
        return 0.0

    def read_int32(self, address: int) -> int:
        """قراءة int32 من الذاكرة"""
        data = self.read_memory(address, 4)
        if len(data) == 4:
            return struct.unpack('<i', data)[0]
        return 0

    def read_int64(self, address: int) -> int:
        """قراءة int64 من الذاكرة"""
        data = self.read_memory(address, 8)
        if len(data) == 8:
            return struct.unpack('<q', data)[0]
        return 0

    def read_pointer(self, address: int) -> int:
        """قراءة مؤشر (64-bit)"""
        return self.read_int64(address)

    def read_vector(self, address: int) -> FVector:
        """قراءة FVector من الذاكرة"""
        x = self.read_float(address)
        y = self.read_float(address + 4)
        z = self.read_float(address + 8)
        return FVector(x, y, z)

    def read_string(self, address: int, max_length: int = 256) -> str:
        """قراءة string من الذاكرة"""
        try:
            data = self.read_memory(address, max_length)
            return data.split(b'\x00')[0].decode('utf-8', errors='ignore')
        except:
            return ""

    def read_matrix(self, address: int) -> FMatrix:
        """قراءة مصفوفة 4x4 من الذاكرة"""
        matrix = []
        for i in range(4):
            row = []
            for j in range(4):
                offset = address + (i * 4 + j) * 4
                row.append(self.read_float(offset))
            matrix.append(row)
        return FMatrix(matrix)


# ============= Detection Engine =============

class ESPDetectionEngine:
    """محرك كشف ESP"""

    def __init__(self, memory_reader: UE4MemoryReader):
        self.reader = memory_reader
        self.detection_history = []
        self.previous_targets = []

    def detect_sudden_aim_change(self, current_targets: List[ESPTarget]) -> List[ESPTarget]:
        """كشف تغيرات حادة في التوجه"""
        detected = []

        if not self.previous_targets:
            self.previous_targets = current_targets
            return detected

        for current in current_targets:
            for previous in self.previous_targets:
                if previous.actor_id == current.actor_id:
                    # حساب التغير في الموقع
                    distance_change = current.distance - previous.distance

                    # إذا كان التغير حاداً جداً (الهدف كان غير مرئي فجأة صار مرئي)
                    if abs(distance_change) > 1000:
                        current.is_detected = True
                        current.detection_method = DetectionMethod.SUDDEN_AIM_CHANGE.value
                        detected.append(current)
                    break

        self.previous_targets = current_targets
        return detected

    def detect_distance_anomaly(self, targets: List[ESPTarget]) -> List[ESPTarget]:
        """كشف شذوذ في المسافات (ESP يسمح برؤية بعيدة جداً)"""
        detected = []
        max_normal_distance = 3000  # المسافة الطبيعية للرؤية

        for target in targets:
            # إذا كان الهدف مرئياً على الشاشة لكن بمسافة غير طبيعية
            if target.is_visible and target.distance > max_normal_distance:
                # احتمال استخدام ESP
                target.is_detected = True
                target.detection_method = DetectionMethod.DISTANCE_ANOMALY.value
                detected.append(target)

        return detected

    def detect_impossible_visibility(self, targets: List[ESPTarget]) -> List[ESPTarget]:
        """كشف رؤية مستحيلة (أهداف خلف الجدران)"""
        detected = []

        for target in targets:
            # إذا كان الهدف على الشاشة لكن في زاوية مستحيلة
            screen_x = target.screen_position.X
            screen_y = target.screen_position.Y

            # إذا كان الهدف في زاوية غريبة جداً مع كونه "مرئياً"
            # قد يكون استخدام cheat للرؤية عبر الجدران
            if ((screen_x < -500 or screen_x > 2500) and
                (screen_y < -500 or screen_y > 1580)):
                target.is_detected = True
                target.detection_method = DetectionMethod.IMPOSSIBLE_VISIBILITY.value
                detected.append(target)

        return detected

    def detect_angle_anomaly(self, targets: List[ESPTarget], player_location: FVector) -> List[ESPTarget]:
        """كشف شذوذ في الزوايا - توجه نحو أهداف مخفية بدقة غريبة"""
        detected = []

        for target in targets:
            if not target.is_visible:
                # الهدف غير مرئي لكن قد يتم التوجه نحوه
                # يمكن كشف هذا من سلوك اللاعب
                angle = self._calculate_angle_to_target(player_location, target.world_position)

                # إذا كان هناك توجه دقيق جداً نحو أهداف غير مرئية
                if angle < 5:  # دقة عالية جداً
                    target.is_detected = True
                    target.detection_method = DetectionMethod.ANGLE_ANOMALY.value
                    detected.append(target)

        return detected

    def run_all_detections(self, targets: List[ESPTarget], player_location: FVector) -> List[ESPTarget]:
        """تشغيل جميع اختبارات الكشف"""
        all_detected = []

        all_detected.extend(self.detect_sudden_aim_change(targets))
        all_detected.extend(self.detect_distance_anomaly(targets))
        all_detected.extend(self.detect_impossible_visibility(targets))
        all_detected.extend(self.detect_angle_anomaly(targets, player_location))

        return all_detected

    @staticmethod
    def _calculate_angle_to_target(player_pos: FVector, target_pos: FVector) -> float:
        """حساب الزاوية بين اللاعب والهدف"""
        dx = target_pos.X - player_pos.X
        dy = target_pos.Y - player_pos.Y

        length = math.sqrt(dx**2 + dy**2)
        if length == 0:
            return 0

        # تطبيع
        dx /= length
        dy /= length

        angle = math.atan2(dy, dx) * 180 / math.pi
        return abs(angle)


# ============= Report Generator =============

class DetectionReport:
    """تقرير الكشف"""

    def __init__(self):
        self.detections = []
        self.total_targets = 0

    def add_detection(self, target: ESPTarget):
        self.detections.append(target)

    def print_report(self):
        print("\n" + "=" * 100)
        print(" " * 35 + "تقرير اختبار نظام كشف ESP")
        print("=" * 100)

        print(f"{'اسم الهدف':<30} {'المسافة (م)':<15} {'على الشاشة':<15} {'مكتشف':<15} {'طريقة الكشف':<25}")
        print("-" * 100)

        detected_count = 0
        for detection in self.detections:
            visible_str = "نعم" if detection.is_visible else "لا"
            detected_str = "نعم ✓" if detection.is_detected else "لا"

            if detection.is_detected:
                detected_count += 1

            print(f"{detection.name:<30} {detection.distance:<15.2f} {visible_str:<15} {detected_str:<15} {detection.detection_method:<25}")

        print("-" * 100)
        print(f"\nالإحصائيات:")
        print(f"  • إجمالي الأهداف: {self.total_targets}")
        print(f"  • الأهداف المكتشفة: {detected_count}")
        detection_rate = (detected_count / self.total_targets * 100) if self.total_targets > 0 else 0
        print(f"  • نسبة الكشف: {detection_rate:.1f}%")
        print("=" * 100)


# ============= Helper Functions =============

def find_game_process():
    """البحث عن عملية اللعبة/المحاكي"""
    print("جاري البحث عن عملية اللعبة...")

    for process in psutil.process_iter(['pid', 'name']):
        try:
            name = process.info['name'].lower()
            pid = process.info['pid']

            # ابحث عن محاكي الأندرويد أو اللعبة
            if any(keyword in name for keyword in ['emulator', 'qemu', 'game', 'ue4']):
                print(f"✓ تم العثور على العملية: {name} (PID: {pid})")
                return pid
        except:
            pass

    print("✗ لم يتم العثور على عملية اللعبة")
    return None


def main():
    print("===== أداة اختبار كشف ESP لـ Unreal Engine 4 =====\n")

    # البحث عن العملية
    game_pid = find_game_process()
    if not game_pid:
        print("الرجاء التأكد من أن المحاكي أو اللعبة تعمل")
        return

    # إنشاء قارئ الذاكرة
    reader = UE4MemoryReader(None)

    # إنشاء محرك الكشف
    detection_engine = ESPDetectionEngine(reader)
    report = DetectionReport()

    # محاكاة قراءة الأهداف
    print("\nجاري محاكاة قراءة الأهداف...")
    print("-" * 50)

    # بيانات تجريبية للاختبار
    player_location = FVector(0, 0, 0)
    test_targets = [
        ESPTarget("Player_1", FVector(100, 50, 0), FVector(960, 540, 1), 111.8, 1, True),
        ESPTarget("Player_2", FVector(-200, 300, 0), FVector(400, 250, 1), 360.6, 2, True),
        ESPTarget("Player_3", FVector(5000, 2000, 0), FVector(1900, 100, -1), 5385.2, 3, False),
        ESPTarget("Enemy_1", FVector(800, -600, 0), FVector(1200, 620, 1), 1000.0, 4, True),
        ESPTarget("Enemy_2", FVector(-1500, 1000, 0), FVector(100, 300, -1), 1802.8, 5, False),
    ]

    # تشغيل الكشف
    detected = detection_engine.run_all_detections(test_targets, player_location)

    # إنشاء التقرير
    report.total_targets = len(test_targets)
    for target in test_targets:
        report.add_detection(target)

    # طباعة التقرير
    report.print_report()

    print("\nملاحظات:")
    print("  • هذه نسخة توضيحية من الأداة")
    print("  • يجب تحديث عناوين الذاكرة حسب إصدار اللعبة")
    print("  • استخدم Cheat Engine لإيجاد العناوين الصحيحة")
    print("  • يمكن إضافة خوارزميات كشف أكثر تقدماً")


if __name__ == "__main__":
    main()
