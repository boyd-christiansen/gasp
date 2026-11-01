#import <AVFoundation/AVFoundation.h>

NS_ASSUME_NONNULL_BEGIN
// AVAudioEngine's legacy tap API can raise NSException, which Swift's do/catch
// cannot catch. Contain it here, before it can unwind a Swift concurrency task.
@interface GaspAudioInput : NSObject
+ (BOOL)startEngine:(AVAudioEngine *)engine tap:(AVAudioNodeTapBlock)tap
              error:(NSError * _Nullable * _Nullable)error NS_SWIFT_NAME(start(_:tap:));
+ (void)stopEngine:(AVAudioEngine *)engine NS_SWIFT_NAME(stop(_:));
@end
NS_ASSUME_NONNULL_END
