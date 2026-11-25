// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "MusicDesktop",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Halo", targets: ["Halo"]),
        .executable(name: "Lyra", targets: ["Lyra"]),
        .executable(name: "Wave", targets: ["Wave"]),
    ],
    targets: [
        // Pure Foundation: builds and tests on Linux too.
        .target(name: "LyricsKit"),
        .target(name: "SharedKit"),
        .executableTarget(name: "Halo", dependencies: ["SharedKit"]),
        .executableTarget(name: "Lyra", dependencies: ["SharedKit", "LyricsKit"]),
        .executableTarget(name: "Wave", dependencies: ["SharedKit"]),
        .testTarget(name: "LyricsKitTests", dependencies: ["LyricsKit"]),
    ]
)
