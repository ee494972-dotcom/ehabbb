# دليل إعداد أداة اختبار كشف ESP لـ UE4

## مقدمة
هذا الدليل يشرح كيفية إعداد واستخدام أداة اختبار كشف ESP (عرض موقع اللاعبين) لمحرك Unreal Engine 4.

---

## 1. المتطلبات

### للبيئة الكمبيوترية:
- **نظام التشغيل**: Windows 10/11
- **C++ Compiler**: Visual Studio 2019+ مع C++ support
- **Python**: إصدار 3.8+
- **محاكي الأندرويد**: Android Emulator أو أي محاكي آخر

### المكتبات المطلوبة (Python):
```bash
pip install psutil pywin32 ctypes-structpacking
```

---

## 2. إيجاد عناوين الذاكرة (العنوان الأصعب)

### استخدام Cheat Engine:

1. **تحميل Cheat Engine**
   - من موقع: https://www.cheatengine.org/
   - قم بتثبيته على جهازك

2. **فتح اللعبة والمحاكي**
   - شغّل اللعبة على محاكي الأندرويد
   - شغّل Cheat Engine

3. **اختيار العملية**
   - انقر على "File" → "Open Process"
   - اختر عملية محاكي الأندرويد (قد تكون `qemu-system-x86_64.exe` أو `emulator.exe`)

4. **البحث عن GWorld**
   - GWorld هو مؤشر عام يشير إلى العالم الحالي في UE4
   - في Cheat Engine، استخدم "Scan" للبحث عن patterns معروفة
   - أو ابحث عن opcode signature خاص بـ GWorld

   ```
   // Pattern معروف لـ GWorld في معظم الألعاب المبنية على UE4
   // ابحث عن:
   48 8B 0D ? ? ? ? 48 85 C9
   ```

5. **البحث عن PersistentLevel**
   - بعد العثور على GWorld، ستجد offset يشير إلى PersistentLevel
   - عادةً يكون الـ offset حوالي 0x30

6. **البحث عن Actors Array**
   - داخل PersistentLevel، هناك مصفوفة تحتوي على جميع الكائنات في المستوى
   - الـ offset عادةً حوالي 0x98 أو 0xA0

### مثال على البحث اليدوي:

```
GWorld Address: 0x[xxxxxxxx]
PersistentLevel = *(&GWorld + 0x30)
ActorsArray = *(PersistentLevel + 0x98)
```

---

## 3. تجميع برنامج C++

### خطوات التجميع:

```batch
# افتح Visual Studio Command Prompt
cd path\to\your\project

# تجميع الملف
cl.exe /EHsc UE4ESPDetectionTester.cpp /link kernel32.lib psapi.lib

# أو استخدام CMake (مفضل)
```

### ملف CMakeLists.txt:

```cmake
cmake_minimum_required(VERSION 3.10)
project(UE4ESPDetectionTester)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(UE4Tester UE4ESPDetectionTester.cpp)

target_link_libraries(UE4Tester kernel32 psapi)
```

---

## 4. تشغيل برنامج Python

### بسيط جداً:

```bash
python ue4_esp_tester.py
```

### مع وسائط خاصة:

```bash
python ue4_esp_tester.py --pid 1234 --gworld 0x[address]
```

---

## 5. تحديث العناوين في الكود

### في `UE4ESPDetectionTester.cpp`:

```cpp
UE4Offsets GetOffsets()
{
    UE4Offsets Offsets;
    
    // ضع العناوين التي عثرت عليها من Cheat Engine هنا
    Offsets.GWorld = 0x[your_gworld_address];
    Offsets.GNames = 0x[your_gnames_address];
    Offsets.GObjects = 0x[your_gobjects_address];
    
    // ضع الـ offsets
    Offsets.PersistentLevelOffset = 0x30;  // قد يختلف
    Offsets.ActorsArrayOffset = 0x98;      // قد يختلف
    
    return Offsets;
}
```

### في `ue4_esp_tester.py`:

لا تحتاج لتحديث عناوين لأن نسخة Python توضيحية تستخدم بيانات اختبار.

---

## 6. خوارزميات الكشف المستخدمة

### 1. كشف تغيرات الحركة الحادة (Sudden Aim Changes)
```
إذا قفز اللاعب من استهداف إلى آخر بسرعة غريبة
→ قد يستخدم ESP
```

### 2. كشف المسافات الشاذة (Distance Anomaly)
```
إذا كان الهدف مرئياً على الشاشة لكن على مسافة > 3000 متر
→ قد يستخدم ESP ليرى بعيداً جداً
```

### 3. كشف الرؤية المستحيلة (Impossible Visibility)
```
إذا كان الهدف خلف جدران لكن يُرسم على الشاشة
→ يستخدم Wall Hacks أو ESP
```

### 4. كشف الزوايا الشاذة (Angle Anomaly)
```
إذا كان اللاعب يوجه نحو أهداف غير مرئية بدقة غريبة
→ قد يستخدم Aimbot + ESP
```

---

## 7. تحسينات يمكن إضافتها

### تتبع السلوك عبر الوقت:
```cpp
// احتفظ بسجل لحركات اللاعب في آخر 10 ثوانٍ
std::deque<PlayerSnapshot> PlayerHistory;

// حلل الأنماط
if (DetectSuspiciousPattern(PlayerHistory))
{
    // توجه مريب جداً نحو أهداف مخفية
}
```

### استخدام Machine Learning:
```python
# تدريب نموذج على سلوك اللاعبين الطبيعيين
from sklearn.ensemble import IsolationForest

model = IsolationForest(contamination=0.1)
predictions = model.fit_predict(player_movements)
```

### كشف بناءً على Network Traffic:
```
مراقبة حزم الشبكة المرسلة من اللعبة
إذا كان اللاعب يتحرك نحو أهداف غير مرئية
لكن يستقبل معلومات عنهم من السيرفر
→ قد يكون cheater
```

### فحص الملفات المُعدّلة:
```python
# افحص أيّ modders أو DLLs غريبة محقونة في العملية
import os
dll_path = "game/plugins/"

for dll in os.listdir(dll_path):
    if not is_authorized(dll):
        print(f"⚠️ DLL غريبة مكتشفة: {dll}")
```

---

## 8. الأخطاء الشائعة والحلول

| المشكلة | السبب | الحل |
|--------|------|-----|
| "خطأ في فتح العملية" | العملية غير موجودة أو الصلاحيات غير كافية | شغّل البرنامج كـ Administrator |
| "قيم عناوين خاطئة" | العناوين لا تطابق إصدار اللعبة | استخدم Cheat Engine لإيجاد العناوين الصحيحة |
| "لا توجد أهداف" | مصفوفة Actors فارغة أو عنوان خاطئ | تحقق من offset الـ ActorsArray |
| "crash عند القراءة" | عنوان غير صحيح | أضف checks للعناوين قبل القراءة |

---

## 9. أمثلة الاستخدام

### مراقبة في الوقت الفعلي:

```cpp
while (true)
{
    // قراءة بيانات اللعبة
    auto Targets = Reader.GetVisibleTargets(...);
    
    // تحليلها
    auto Detected = DetectionEngine.RunAllDetections(Targets, PlayerLocation);
    
    // تسجيل النتائج
    for (auto& Target : Detected)
    {
        std::cout << "⚠️ مريب: " << Target.Name 
                  << " (" << Target.DetectionMethod << ")" << std::endl;
    }
    
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
}
```

### التقارير:

```python
# يتم إنشاء تقرير شامل يوضح:
# • عدد الأهداف المكتشفة
# • طرق الكشف المستخدمة
# • المعدل الكلي للاكتشاف
# • الإيجابيات الكاذبة
```

---

## 10. ملاحظات أمنية مهمة

✅ **استخدم هذه الأداة فقط على:**
- اللعبة التي طورتها أنت
- محاكيات/اختبارات تملكها أنت
- في بيئة تطوير آمنة

❌ **لا تستخدمها على:**
- ألعاب الآخرين
- خوادم عامة
- بدون تصريح صريح من المالك

---

## 11. المراجع والموارد

- [Unreal Engine Memory Layout](https://docs.unrealengine.com/)
- [Cheat Engine Tutorials](https://www.youtube.com/watch?v=hksKvjlAJx8)
- [Windows API Documentation](https://docs.microsoft.com/en-us/windows/win32/apiindex/windows-api-list)
- [Anti-Cheat Systems Analysis](https://www.aucklanduni.ac.nz/)

---

## الخلاصة

هذه الأداة توفر:
1. ✅ قراءة آمنة من ذاكرة العملية
2. ✅ كشف متعدد الطرق للـ ESP
3. ✅ تقارير مفصلة عن السلوك المريب
4. ✅ قابلية التوسع والتحسين

**استخدمها بحكمة لحماية لعبتك من الغش!** 🛡️
