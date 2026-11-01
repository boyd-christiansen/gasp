#import "AudioInput.h"

@implementation GaspAudioInput
+ (BOOL)startEngine:(AVAudioEngine *)engine tap:(AVAudioNodeTapBlock)tap error:(NSError **)error {
    @try {
        AVAudioInputNode *input = engine.inputNode;
        if (input.isVoiceProcessingEnabled && ![input setVoiceProcessingEnabled:NO error:error]) return NO;
        AVAudioFormat *hardware = [input inputFormatForBus:0];
        if (hardware.sampleRate <= 0 || hardware.channelCount == 0) {
            if (error) *error = [NSError errorWithDomain:@"Gasp.AudioInput" code:1
                userInfo:@{NSLocalizedDescriptionKey:@"No microphone input is available."}];
            return NO;
        }
        // Adopt the fresh engine's negotiated format rather than forcing the
        // previous device's rate onto a newly selected input.
        [input installTapOnBus:0 bufferSize:1024 format:nil block:tap];
        [engine prepare];
        if ([engine startAndReturnError:error]) return YES;
    } @catch (NSException *exception) {
        if (error) *error = [NSError errorWithDomain:@"Gasp.AudioInput" code:2
            userInfo:@{NSLocalizedDescriptionKey:@"The microphone changed while starting. Check your input device and try again.",
                       NSDebugDescriptionErrorKey:exception.reason ?: exception.name}];
    }
    [self stopEngine:engine];
    return NO;
}
+ (void)stopEngine:(AVAudioEngine *)engine {
    @try { [engine stop]; [engine.inputNode removeTapOnBus:0]; }
    @catch (NSException *exception) { NSLog(@"Gasp audio cleanup: %@", exception.reason); }
}
@end
