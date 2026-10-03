#include "UE4MemoryReader.h"
#include <iostream>
#include <thread>
#include <chrono>
#include <iomanip>

// ============= Configuration =============

// تحتاج تحديث هذه العناوين حسب اللعبة والمحاكي
UE4Offsets GetOffsets()
{
    UE4Offsets Offsets;

    // قيم تجريبية - يجب تحديثها حسب اللعبة المحددة
    // استخدم Cheat Engine لإيجاد العناوين الفعلية
    Offsets.GWorld = 0x0;  // ضع العنوان الفعلي للعبة
    Offsets.GNames = 0x0;
    Offsets.GObjects = 0x0;

    // Offsets داخل الهياكل
    Offsets.PersistentLevelOffset = 0x30;
    Offsets.ActorsArrayOffset = 0x98;

    return Offsets;
}

// ============= Logging and Reporting =============

class DetectionReport
{
public:
    struct Detection
    {
        std::string TargetName;
        float Distance;
        bool WasOnScreen;
        bool WasDetected;
        std::string DetectionMethod;
    };

    std::vector<Detection> Detections;

    void AddDetection(
        const std::string& Name,
        float Distance,
        bool OnScreen,
        bool Detected,
        const std::string& Method
    )
    {
        Detections.push_back({Name, Distance, OnScreen, Detected, Method});
    }

    void PrintReport()
    {
        std::cout << "\n" << std::string(80, '=') << std::endl;
        std::cout << "           تقرير اختبار نظام كشف ESP" << std::endl;
        std::cout << std::string(80, '=') << std::endl;

        std::cout << std::left
                  << std::setw(25) << "اسم الهدف"
                  << std::setw(15) << "المسافة (م)"
                  << std::setw(15) << "على الشاشة"
                  << std::setw(15) << "مكتشف"
                  << std::setw(15) << "طريقة الكشف" << std::endl;
        std::cout << std::string(80, '-') << std::endl;

        int DetectedCount = 0;
        int FalsePositives = 0;
        int FalseNegatives = 0;

        for (const auto& Det : Detections)
        {
            std::string OnScreen = Det.WasOnScreen ? "نعم" : "لا";
            std::string Detected = Det.WasDetected ? "نعم" : "لا";

            if (Det.WasDetected) DetectedCount++;
            if (Det.WasDetected && !Det.WasOnScreen) FalsePositives++;
            if (!Det.WasDetected && Det.WasOnScreen) FalseNegatives++;

            std::cout << std::left
                      << std::setw(25) << Det.TargetName
                      << std::setw(15) << std::fixed << std::setprecision(1) << Det.Distance
                      << std::setw(15) << OnScreen
                      << std::setw(15) << Detected
                      << std::setw(15) << Det.DetectionMethod << std::endl;
        }

        std::cout << std::string(80, '-') << std::endl;
        std::cout << std::endl;
        std::cout << "الإحصائيات:" << std::endl;
        std::cout << "  - إجمالي الأهداف: " << Detections.size() << std::endl;
        std::cout << "  - الأهداف المكتشفة: " << DetectedCount << std::endl;
        std::cout << "  - نسبة الكشف: "
                  << (Detections.empty() ? 0.f : (DetectedCount * 100.f / Detections.size()))
                  << "%" << std::endl;
        std::cout << "  - الإيجابيات الكاذبة: " << FalsePositives << std::endl;
        std::cout << "  - السلبيات الكاذبة: " << FalseNegatives << std::endl;
        std::cout << std::string(80, '=') << std::endl;
    }
};

// ============= ESP Detection Algorithms =============

class ESPDetectionEngine
{
private:
    UE4MemoryReader& Reader;
    DetectionReport Report;

public:
    ESPDetectionEngine(UE4MemoryReader& InReader)
        : Reader(InReader) {}

    // كشف متقدم بناءً على الخوارزميات المختلفة
    void RunDetectionTests(
        const std::vector<UE4MemoryReader::ESPTarget>& Targets,
        const FVector& PlayerLocation
    )
    {
        for (const auto& Target : Targets)
        {
            bool Detected = false;
            std::string DetectionMethod = "لم يتم الكشف";

            // ===== Test 1: Sudden Aim Changes (متغيرات الحركة المريبة) =====
            if (DetectSuspiciousAimBehavior(Target))
            {
                Detected = true;
                DetectionMethod = "كشف الحركة الغريبة";
            }

            // ===== Test 2: Wall Hacking Detection (عبور الجدران) =====
            if (DetectWallHacking(Target, PlayerLocation))
            {
                Detected = true;
                DetectionMethod = "كشف عبور الجدران";
            }

            // ===== Test 3: Distance-based Detection (كشف بناءً على المسافة) =====
            if (Target.Distance > 3000.f && Target.IsVisible)
            {
                Detected = true;
                DetectionMethod = "كشف رؤية بعيدة المدى";
            }

            // ===== Test 4: Angle-based Detection (كشف الزوايا المريبة) =====
            float SuspiciousAngle = CalculateSuspiciousAngle(Target, PlayerLocation);
            if (SuspiciousAngle > 45.f && Target.IsVisible)
            {
                Detected = true;
                DetectionMethod = "كشف الزاوية المريبة";
            }

            Report.AddDetection(
                Target.Name,
                Target.Distance,
                Target.IsVisible,
                Detected,
                DetectionMethod
            );
        }
    }

    bool DetectSuspiciousAimBehavior(const UE4MemoryReader::ESPTarget& Target)
    {
        // كشف تغيرات حادة في التوجه نحو أهداف خارج نطاق الرؤية
        // (يتطلب سجل تاريخي للحركات - يمكن إضافته لاحقاً)
        return false;
    }

    bool DetectWallHacking(
        const UE4MemoryReader::ESPTarget& Target,
        const FVector& PlayerLocation
    )
    {
        // كشف إطلاق النار عبر الجدران على أهداف مخفية
        // (يتطلب نموذج العالم ثلاثي الأبعاد - raycasting)

        // مثال بسيط: إذا كان الهدف غير مرئي ولكن تم إطلاق النار عليه
        // يمكن كشفه من خلال سجل الأضرار
        return false;
    }

    float CalculateSuspiciousAngle(
        const UE4MemoryReader::ESPTarget& Target,
        const FVector& PlayerLocation
    )
    {
        // حساب الزاوية بين اتجاه اللاعب والهدف
        FVector Direction = Target.WorldPosition;
        Direction.X -= PlayerLocation.X;
        Direction.Y -= PlayerLocation.Y;

        float Length = std::sqrt(
            Direction.X * Direction.X + Direction.Y * Direction.Y
        );

        if (Length == 0.f) return 0.f;

        // تطبيع الاتجاه
        Direction.X /= Length;
        Direction.Y /= Length;

        // حساب الزاوية (يمكن تحسينها بناءً على اتجاه المشهد الفعلي)
        float Angle = std::atan2(Direction.Y, Direction.X) * 180.f / 3.14159f;
        return std::abs(Angle);
    }

    void PrintReport()
    {
        Report.PrintReport();
    }
};

// ============= Main Program =============

bool FindGameProcess(uint64_t& OutPID)
{
    // البحث عن عملية المحاكي أو اللعبة
    // قد تحتاج إلى تخصيص هذا حسب محاكي الأندرويد الذي تستخدمه

    DWORD ProcessIDs[1024];
    DWORD BytesReturned;

    if (!EnumProcesses(ProcessIDs, sizeof(ProcessIDs), &BytesReturned))
    {
        std::cerr << "فشل تعداد العمليات" << std::endl;
        return false;
    }

    DWORD NumProcesses = BytesReturned / sizeof(DWORD);

    // ابحث عن محاكي الأندرويد (اسم العملية قد يختلف)
    // أمثلة: qemu-system-x86_64.exe (Emulator)، emulator.exe، etc

    for (DWORD i = 0; i < NumProcesses; ++i)
    {
        HANDLE Process = OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
            FALSE,
            ProcessIDs[i]
        );

        if (Process)
        {
            char ProcessName[MAX_PATH];
            GetModuleBaseNameA(Process, nullptr, ProcessName, sizeof(ProcessName));

            // ابحث عن محاكي الأندرويد
            std::string Name(ProcessName);
            if (Name.find("emulator") != std::string::npos ||
                Name.find("qemu") != std::string::npos)
            {
                OutPID = ProcessIDs[i];
                CloseHandle(Process);
                return true;
            }

            CloseHandle(Process);
        }
    }

    std::cerr << "لم يتم العثور على عملية اللعبة" << std::endl;
    return false;
}

int main()
{
    std::cout << "===== أداة اختبار كشف ESP لـ UE4 =====" << std::endl;
    std::cout << "جاري البحث عن عملية اللعبة..." << std::endl;

    uint64_t GamePID = 0;
    if (!FindGameProcess(GamePID))
    {
        std::cerr << "خطأ: لم يتم العثور على اللعبة" << std::endl;
        return 1;
    }

    std::cout << "تم العثور على اللعبة - PID: " << GamePID << std::endl;

    // إنشاء الـ offsets (تحتاج تحديثها بناءً على لعبتك)
    UE4Offsets Offsets = GetOffsets();

    // إنشاء قارئ الذاكرة
    UE4MemoryReader Reader(GamePID, Offsets);

    if (!Reader.IsValid())
    {
        std::cerr << "فشل الاتصال بذاكرة اللعبة" << std::endl;
        return 1;
    }

    std::cout << "تم الاتصال بنجاح بذاكرة اللعبة" << std::endl;

    // حلقة المراقبة الرئيسية
    ESPDetectionEngine DetectionEngine(Reader);

    std::cout << "\nجاري قراءة بيانات اللعبة... (اضغط Ctrl+C للإيقاف)" << std::endl;
    std::cout << std::string(80, '-') << std::endl;

    while (true)
    {
        try
        {
            // قراءة GWorld
            uint64_t WorldAddr = Reader.GetGWorld();
            if (!WorldAddr) {
                std::cerr << "خطأ: لم يتم العثور على GWorld" << std::endl;
                continue;
            }

            // قراءة PersistentLevel
            uint64_t LevelAddr = Reader.GetPersistentLevel(WorldAddr);
            if (!LevelAddr) {
                std::cerr << "خطأ: لم يتم العثور على PersistentLevel" << std::endl;
                continue;
            }

            // قراءة مصفوفة الأهداف
            FActorArray ActorsArray = Reader.GetActorsArray(LevelAddr);
            if (!ActorsArray.Data || ActorsArray.Num <= 0) {
                std::cerr << "خطأ: مصفوفة الأهداف فارغة" << std::endl;
                continue;
            }

            // قراءة موقع اللاعب الرئيسي (يحتاج تحديد عنوان صحيح)
            // هذا مثال توضيحي
            FVector PlayerLocation = Reader.ReadActorLocation(WorldAddr);

            // الحصول على الأهداف المرئية
            std::vector<UE4MemoryReader::ESPTarget> Targets =
                Reader.GetVisibleTargets(
                    PlayerLocation,
                    FMatrix(),  // قراءة ViewMatrix من اللعبة
                    reinterpret_cast<uint64_t>(ActorsArray.Data),
                    ActorsArray.Num
                );

            // تشغيل اختبارات الكشف
            DetectionEngine.RunDetectionTests(Targets, PlayerLocation);

            // انتظار قبل الفحص التالي
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }
        catch (const std::exception& ex)
        {
            std::cerr << "خطأ أثناء القراءة: " << ex.what() << std::endl;
        }
    }

    return 0;
}
