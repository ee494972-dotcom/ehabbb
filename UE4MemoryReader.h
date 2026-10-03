#pragma once
#include <windows.h>
#include <vector>
#include <cmath>
#include <iostream>
#include <algorithm>

// ============= UE4 Structures =============

struct FVector
{
    float X, Y, Z;

    float Distance(const FVector& Other) const
    {
        float DX = X - Other.X;
        float DY = Y - Other.Y;
        float DZ = Z - Other.Z;
        return std::sqrt(DX * DX + DY * DY + DZ * DZ);
    }
};

struct FMatrix
{
    float M[4][4];
};

struct FTransform
{
    float Rotation[4];  // Quaternion
    FVector Translation;
    FVector Scale3D;
};

struct AActor
{
    uint64_t VTable;
    FVector ActorLocation;
    FTransform RootComponent;
    char ActorName[256];
    uint32_t ActorID;
};

struct ACharacter : public AActor
{
    float Health;
    float MaxHealth;
    uint32_t Team;
};

struct FActorArray
{
    AActor** Data;
    int32_t Num;
    int32_t Max;
};

// ============= UE4 Engine Addresses =============
// هذه العناوين تختلف حسب إصدار UE4 والمحاكي
// يجب تحديثها حسب اللعبة الخاصة بك

struct UE4Offsets
{
    uint64_t GWorld;                    // GWorld pointer address
    uint64_t GNames;                    // GNames array
    uint64_t GObjects;                  // GObjects array

    // Offsets داخل UWorld
    uint64_t PersistentLevelOffset;     // Offset to PersistentLevel
    uint64_t ActorsArrayOffset;         // Offset to Actors array in Level
};

// ============= Memory Reader Class =============

class UE4MemoryReader
{
private:
    HANDLE ProcessHandle;
    uint64_t ProcessID;
    UE4Offsets Offsets;

public:
    UE4MemoryReader(uint64_t PID, const UE4Offsets& InOffsets)
        : ProcessID(PID), Offsets(InOffsets)
    {
        ProcessHandle = OpenProcess(
            PROCESS_VM_READ | PROCESS_QUERY_INFORMATION,
            FALSE,
            static_cast<DWORD>(PID)
        );

        if (!ProcessHandle)
        {
            std::cerr << "فشل فتح العملية - خطأ: " << GetLastError() << std::endl;
        }
    }

    ~UE4MemoryReader()
    {
        if (ProcessHandle)
        {
            CloseHandle(ProcessHandle);
        }
    }

    bool IsValid() const { return ProcessHandle != nullptr; }

    // ===== Core Memory Reading Functions =====

    bool ReadMemory(uint64_t Address, void* Buffer, size_t Size)
    {
        SIZE_T BytesRead = 0;
        return ReadProcessMemory(
            ProcessHandle,
            reinterpret_cast<LPCVOID>(Address),
            Buffer,
            Size,
            &BytesRead
        ) && BytesRead == Size;
    }

    template<typename T>
    bool Read(uint64_t Address, T& OutValue)
    {
        return ReadMemory(Address, &OutValue, sizeof(T));
    }

    uint64_t ReadPointer(uint64_t Address)
    {
        uint64_t Ptr = 0;
        Read<uint64_t>(Address, Ptr);
        return Ptr;
    }

    std::string ReadString(uint64_t Address, size_t MaxLength = 256)
    {
        char Buffer[512] = { 0 };
        ReadMemory(Address, Buffer, std::min(MaxLength, size_t(512)));
        return std::string(Buffer);
    }

    // ===== UE4 Specific Functions =====

    uint64_t GetGWorld()
    {
        return ReadPointer(Offsets.GWorld);
    }

    uint64_t GetPersistentLevel(uint64_t WorldAddr)
    {
        return ReadPointer(WorldAddr + Offsets.PersistentLevelOffset);
    }

    FActorArray GetActorsArray(uint64_t LevelAddr)
    {
        FActorArray Array = { nullptr, 0, 0 };
        ReadMemory(
            LevelAddr + Offsets.ActorsArrayOffset,
            &Array,
            sizeof(FActorArray)
        );
        return Array;
    }

    bool ReadActor(uint64_t ActorAddr, AActor& OutActor)
    {
        return ReadMemory(ActorAddr, &OutActor, sizeof(AActor));
    }

    bool ReadCharacter(uint64_t CharAddr, ACharacter& OutChar)
    {
        return ReadMemory(CharAddr, &OutChar, sizeof(ACharacter));
    }

    FVector ReadActorLocation(uint64_t ActorAddr)
    {
        FVector Location = { 0, 0, 0 };
        // Location عادة تكون في offset محدد من AActor
        ReadMemory(ActorAddr + 0x120, &Location, sizeof(FVector));
        return Location;
    }

    // ===== View Matrix and Screen Space Calculations =====

    FMatrix ReadViewMatrix(uint64_t PlayerControllerAddr)
    {
        FMatrix ViewMatrix = {};
        // ViewMatrix عادة تكون في PlayerController
        ReadMemory(PlayerControllerAddr + 0x380, &ViewMatrix, sizeof(FMatrix));
        return ViewMatrix;
    }

    FVector WorldToScreenSpace(
        const FVector& WorldPos,
        const FMatrix& ViewMatrix,
        int ScreenWidth,
        int ScreenHeight
    )
    {
        // تحويل من World Space إلى Screen Space
        float X = ViewMatrix.M[0][0] * WorldPos.X +
                 ViewMatrix.M[0][1] * WorldPos.Y +
                 ViewMatrix.M[0][2] * WorldPos.Z +
                 ViewMatrix.M[0][3];

        float Y = ViewMatrix.M[1][0] * WorldPos.X +
                 ViewMatrix.M[1][1] * WorldPos.Y +
                 ViewMatrix.M[1][2] * WorldPos.Z +
                 ViewMatrix.M[1][3];

        float Z = ViewMatrix.M[2][0] * WorldPos.X +
                 ViewMatrix.M[2][1] * WorldPos.Y +
                 ViewMatrix.M[2][2] * WorldPos.Z +
                 ViewMatrix.M[2][3];

        float W = ViewMatrix.M[3][0] * WorldPos.X +
                 ViewMatrix.M[3][1] * WorldPos.Y +
                 ViewMatrix.M[3][2] * WorldPos.Z +
                 ViewMatrix.M[3][3];

        if (W != 0.f)
        {
            X /= W;
            Y /= W;
        }

        // تحويل إلى Screen Space
        float ScreenX = (X / 2.f + 0.5f) * ScreenWidth;
        float ScreenY = (0.5f - Y / 2.f) * ScreenHeight;

        return FVector{ ScreenX, ScreenY, Z };
    }

    // ===== Detection Functions =====

    struct ESPTarget
    {
        std::string Name;
        FVector WorldPosition;
        FVector ScreenPosition;
        float Distance;
        uint32_t ActorID;
        bool IsVisible;
    };

    std::vector<ESPTarget> GetVisibleTargets(
        const FVector& PlayerLocation,
        const FMatrix& ViewMatrix,
        uint64_t ActorArrayAddr,
        int32_t ActorCount,
        int ScreenWidth = 1920,
        int ScreenHeight = 1080,
        float MaxDistance = 5000.f
    )
    {
        std::vector<ESPTarget> Targets;

        for (int32_t i = 0; i < ActorCount; ++i)
        {
            uint64_t ActorPtrAddr = ActorArrayAddr + (i * sizeof(uint64_t));
            uint64_t ActorAddr = ReadPointer(ActorPtrAddr);

            if (!ActorAddr) continue;

            AActor Actor = {};
            if (!ReadActor(ActorAddr, Actor)) continue;

            FVector Distance3D = Actor.ActorLocation.Distance(PlayerLocation);
            if (Distance3D > MaxDistance) continue;

            // تحويل إلى Screen Space
            FVector ScreenPos = WorldToScreenSpace(
                Actor.ActorLocation,
                ViewMatrix,
                ScreenWidth,
                ScreenHeight
            );

            // تحديد ما إذا كان على الشاشة
            bool OnScreen = ScreenPos.X >= 0 && ScreenPos.X < ScreenWidth &&
                           ScreenPos.Y >= 0 && ScreenPos.Y < ScreenHeight &&
                           ScreenPos.Z > 0;

            ESPTarget Target;
            Target.Name = Actor.ActorName;
            Target.WorldPosition = Actor.ActorLocation;
            Target.ScreenPosition = ScreenPos;
            Target.Distance = Distance3D;
            Target.ActorID = Actor.ActorID;
            Target.IsVisible = OnScreen;

            Targets.push_back(Target);
        }

        return Targets;
    }

    // ===== Scanning and Finding Addresses =====

    bool ScanForPattern(
        uint64_t StartAddr,
        uint64_t EndAddr,
        const uint8_t* Pattern,
        const uint8_t* Mask,
        size_t PatternSize,
        std::vector<uint64_t>& OutAddresses
    )
    {
        std::vector<uint8_t> Buffer((EndAddr - StartAddr) + 1);

        if (!ReadMemory(StartAddr, Buffer.data(), Buffer.size()))
        {
            return false;
        }

        for (size_t i = 0; i <= Buffer.size() - PatternSize; ++i)
        {
            bool Match = true;
            for (size_t j = 0; j < PatternSize; ++j)
            {
                if ((Buffer[i + j] & Mask[j]) != Pattern[j])
                {
                    Match = false;
                    break;
                }
            }

            if (Match)
            {
                OutAddresses.push_back(StartAddr + i);
            }
        }

        return true;
    }
};
