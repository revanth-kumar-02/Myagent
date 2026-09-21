import 'package:flutter/material.dart';

class VoiceControlsWidget extends StatelessWidget {
  final bool isListening;
  final bool isMuted;
  final bool isSpeaking;
  final VoidCallback onToggleListen;
  final VoidCallback onToggleMute;
  final VoidCallback onInterrupt;

  const VoiceControlsWidget({
    super.key,
    required this.isListening,
    required this.isMuted,
    required this.isSpeaking,
    required this.onToggleListen,
    required this.onToggleMute,
    required this.onInterrupt,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Mute / Unmute
        IconButton.filledTonal(
          icon: Icon(isMuted ? Icons.mic_off : Icons.mic),
          tooltip: isMuted ? 'Unmute Microphone' : 'Mute Microphone',
          onPressed: onToggleMute,
        ),
        const SizedBox(width: 16),
        // Primary Listen / Stop
        FloatingActionButton.large(
          elevation: 2,
          backgroundColor: isListening ? Colors.red : Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          onPressed: onToggleListen,
          tooltip: isListening ? 'Stop Listening' : 'Start Voice Assistant',
          child: Icon(isListening ? Icons.stop : Icons.mic_none, size: 36),
        ),
        const SizedBox(width: 16),
        // Barge-In Interrupt Button
        IconButton.filledTonal(
          icon: const Icon(Icons.back_hand_outlined),
          tooltip: 'Interrupt Speech (Barge-In)',
          onPressed: isSpeaking ? onInterrupt : null,
        ),
      ],
    );
  }
}
