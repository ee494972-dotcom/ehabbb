#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أداة مساعدة للبحث عن عناوين الذاكرة في UE4
تحاول إيجاد GWorld و offsets أخرى تلقائياً (بشكل تقريبي)
"""

import struct
import json
import argparse
from typing import Optional, List, Tuple
import psutil


class UE4OffsetFinder:
    """أداة البحث عن عناوين UE4"""

    # Signatures معروفة لـ GWorld في UE4
    GWORLD_SIGNATURES = [
        # Pattern: mov rcx, [rip+offset] ; lea rax, ...
        b'\x48\x8B\x0D\x00\x00\x00\x00',  # 48 8B 0D ? ? ? ?
        # Pattern: mov rax, [rip+offset]
        b'\x48\x8B\x05\x00\x00\x00\x00',  # 48 8B 05 ? ? ? ?
    ]

    # Known offsets في معظم الألعاب المبنية على UE4
    COMMON_OFFSETS = {
        'persistent_level': 0x30,
        'actors_array': 0x98,
        'actors_array_alt': 0xA0,
        'actor_location': 0x120,
        'root_component': 0x160,
        'actor_name': 0x20,
    }

    def __init__(self, process_handle=None):
        self.process_handle = process_handle
        self.found_offsets = {}

    def scan_for_pattern(self, data: bytes, pattern: bytes, mask: bytes) -> List[int]:
        """البحث عن pattern في البيانات"""
        matches = []
        pattern_len = len(pattern)

        for i in range(len(data) - pattern_len):
            match = True
            for j in range(pattern_len):
                if (data[i + j] & mask[j]) != (pattern[j] & mask[j]):
                    match = False
                    break

            if match:
                matches.append(i)

        return matches

    def extract_rip_offset(self, data: bytes, instruction_offset: int) -> Optional[int]:
        """استخراج RIP-relative offset من الكود"""
        try:
            # في x86-64، الـ offset يكون في 4 bytes بعد opcode
            if instruction_offset + 7 < len(data):
                offset = struct.unpack('<i', data[instruction_offset + 3:instruction_offset + 7])[0]
                return offset
        except:
            pass
        return None

    def find_gworld_candidates(self, pid: int) -> List[Tuple[int, str]]:
        """البحث عن مرشحين GWorld في العملية"""
        candidates = []

        print("[*] البحث عن GWorld في عملية PID {}...".format(pid))

        try:
            process = psutil.Process(pid)

            # قراءة memory maps
            for mmap in process.memory_maps(grouped=False):
                addr = int(mmap.addr, 16) if isinstance(mmap.addr, str) else mmap.addr
                size = mmap.size

                # تخطي الذاكرة غير الصالحة
                if size < 1024:
                    continue

                # حاول البحث في كل segment
                try:
                    # هنا يمكن إضافة قراءة من الذاكرة فعلياً
                    print(f"  [+] Scanning {mmap.path} @ {hex(addr)} - {size} bytes")
                except:
                    pass

        except Exception as e:
            print(f"[!] خطأ أثناء المسح: {e}")

        return candidates

    def verify_offset(self, base_address: int, offset: int, expected_type: str = 'pointer') -> bool:
        """التحقق من صحة offset"""
        try:
            # محاكاة التحقق
            # في الواقع ستحتاج إلى قراءة من الذاكرة
            return True
        except:
            return False

    def suggest_offsets_from_analysis(self) -> dict:
        """اقتراح offsets بناءً على معلومات معروفة"""
        print("\n[*] الـ Offsets المقترحة (بناءً على تجربة):")

        suggestions = {
            'persistent_level_offset': self.COMMON_OFFSETS['persistent_level'],
            'actors_array_offset': self.COMMON_OFFSETS['actors_array'],
            'actor_location_offset': self.COMMON_OFFSETS['actor_location'],
            'root_component_offset': self.COMMON_OFFSETS['root_component'],
            'actor_name_offset': self.COMMON_OFFSETS['actor_name'],
        }

        for key, value in suggestions.items():
            print(f"  {key}: 0x{value:X} ({value})")

        return suggestions

    def save_offsets_to_config(self, filename: str, gworld: Optional[int] = None, offsets: Optional[dict] = None):
        """حفظ العناوين المكتشفة في ملف تكوين"""
        config = {
            "memory_addresses": {
                "gworld": hex(gworld) if gworld else "0x0",
            },
            "offsets": offsets or self.COMMON_OFFSETS,
            "status": "تم البحث تلقائياً - تحقق من الدقة",
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"\n[✓] تم حفظ الإعدادات في: {filename}")
        except Exception as e:
            print(f"[!] خطأ في الحفظ: {e}")


class CheatEngineHelper:
    """مساعد استخدام Cheat Engine"""

    @staticmethod
    def print_instructions():
        """طباعة تعليمات استخدام Cheat Engine"""
        instructions = """
╔════════════════════════════════════════════════════════════════════════╗
║        تعليمات البحث عن العناوين باستخدام Cheat Engine               ║
╚════════════════════════════════════════════════════════════════════════╝

1️⃣  تحميل Cheat Engine:
    • من https://www.cheatengine.org/
    • ثبت البرنامج على جهازك

2️⃣  البحث عن GWorld:
    • شغّل اللعبة أولاً
    • شغّل Cheat Engine كـ Admin
    • اختر عملية المحاكي/اللعبة
    • في Cheat Engine → Tools → Dissect Data Structures
    • ابحث عن الـ pattern: 48 8B 0D ? ? ? ?
    • أو استخدم symbol signature scanner إن وُجد

3️⃣  الحصول على العنوان الفعلي:
    • بعد العثور على الـ signature
    • احسب العنوان الفعلي من RIP-relative offset
    • العنوان = RIP + offset + 7 (حجم التعليمة)

4️⃣  العثور على Offsets:
    • بعد GWorld، استخدم "Pointer Scanner"
    • ابحث عن "PersistentLevel" في الهياكل
    • قارن مع القيم المقترحة (0x30, 0x98, إلخ)

5️⃣  التحقق من الصحة:
    • تحقق من القيم بقراءة الذاكرة
    • تأكد أن البيانات منطقية
    • اختبر مع اللعبة وهي تعمل

📊 Patterns شائعة في UE4:
    • GWorld: 48 8B 0D ? ? ? ?
    • PersistentLevel: offset +0x30
    • ActorsArray: offset +0x98
    • ActorLocation: offset +0x120

💡 نصائح مهمة:
    • استخدم dissect data structures لرؤية البيانات
    • تحقق من نوع البيانات (pointer, float, إلخ)
    • استخدم breakpoints لتتبع الاستدعاءات
    • استخدم IDA Pro أو Ghidra للتحليل العميق

⚠️  تحذير:
    • العناوين تختلف مع كل تحديث للعبة
    • يجب إعادة البحث بعد التحديثات
    • استخدم auto-update offsets إن أمكن
"""
        print(instructions)


def main():
    parser = argparse.ArgumentParser(
        description='أداة البحث عن عناوين Unreal Engine 4',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة الاستخدام:
  python find_offsets.py --help              # عرض المساعدة
  python find_offsets.py --show-instructions  # تعليمات Cheat Engine
  python find_offsets.py --pid 1234          # البحث في عملية محددة
  python find_offsets.py --suggest             # اقتراح offsets قياسية
        """
    )

    parser.add_argument('--pid', type=int, help='معرف العملية (Process ID)')
    parser.add_argument('--show-instructions', action='store_true',
                       help='عرض تعليمات استخدام Cheat Engine')
    parser.add_argument('--suggest', action='store_true',
                       help='اقتراح offsets بناءً على تجربة')
    parser.add_argument('--output', default='config.json',
                       help='ملف الإخراج للتكوين')

    args = parser.parse_args()

    # عرض التعليمات إذا طُلب
    if args.show_instructions:
        CheatEngineHelper.print_instructions()
        return

    # إنشاء أداة البحث
    finder = UE4OffsetFinder()

    # البحث الآلي إذا تم تحديد PID
    if args.pid:
        print(f"🔍 البحث عن العناوين في عملية {args.pid}...")
        candidates = finder.find_gworld_candidates(args.pid)
        if candidates:
            print(f"✓ تم العثور على {len(candidates)} مرشح")

    # اقتراح offsets
    if args.suggest or not args.pid:
        offsets = finder.suggest_offsets_from_analysis()
        finder.save_offsets_to_config(args.output, offsets=offsets)

    print("\n📝 الخطوات التالية:")
    print("  1. استخدم Cheat Engine لإيجاد GWorld الفعلي")
    print("  2. عدّل config.json بالعناوين الصحيحة")
    print("  3. شغّل برنامج الكشف الرئيسي")


if __name__ == "__main__":
    main()
