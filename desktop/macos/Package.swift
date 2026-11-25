// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "MusicDesktop",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Wave", targets: ["Wave"]),
    ],
    targets: [
        // Pure Foundation: builds and tests on Linux too.
        .target(name: "LyricsKit"),
        .target(name: "SharedKit"),
        .executableTarget(name: "Wave", dependencies: ["SharedKit", "LyricsKit"]),
        .testTarget(name: "LyricsKitTests", dependencies: ["LyricsKit"]),
    ]
)
