// No microphone permission or hardware needed. Reproduces an AVFAudio-style
// exception at the tap boundary and verifies it cannot unwind into Swift.
#import "../macos/Sources/AudioInput.h"

@interface FailingInput : NSObject
@end
@implementation FailingInput
- (BOOL)isVoiceProcessingEnabled { return NO; }
- (AVAudioFormat *)inputFormatForBus:(AVAudioNodeBus)bus {
    return [[AVAudioFormat alloc] initStandardFormatWithSampleRate:24000 channels:1];
}
- (void)installTapOnBus:(AVAudioNodeBus)bus bufferSize:(AVAudioFrameCount)size
                format:(AVAudioFormat *)format block:(AVAudioNodeTapBlock)block {
    NSCAssert(format == nil, @"Do not force a stale format on the hardware");
    @throw [NSException exceptionWithName:@"com.apple.coreaudio.avfaudio"
        reason:@"Failed to create tap due to format mismatch" userInfo:nil];
}
- (void)removeTapOnBus:(AVAudioNodeBus)bus {}
@end
@interface FailingEngine : AVAudioEngine
@end
@implementation FailingEngine
- (AVAudioInputNode *)inputNode { return (AVAudioInputNode *)[FailingInput new]; }
- (void)stop {}
@end
int main(void) {
    @autoreleasepool {
        NSError *error=nil;
        BOOL started=[GaspAudioInput startEngine:[FailingEngine new]
            tap:^(AVAudioPCMBuffer *buffer, AVAudioTime *when) {} error:&error];
        NSCAssert(!started && error.code == 2, @"Exception must become a recoverable error");
        puts("Audio exception boundary passed");
    }
    return 0;
}
