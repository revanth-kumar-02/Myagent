import 'package:flutter/material.dart';

class VoiceWaveformWidget extends StatelessWidget {
  final String voiceState;
  final bool isMuted;

  const VoiceWaveformWidget({
    super.key,
    required this.voiceState,
    this.isMuted = false,
  });

  Color _getStateColor(String state) {
    switch (state.toLowerCase()) {
      case 'listening':
        return Colors.green;
      case 'transcribing':
      case 'thinking':
        return Colors.orange;
      case 'speaking':
        return Colors.blue;
      case 'interrupted':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    final stateColor = _getStateColor(voiceState);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: stateColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: stateColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  color: stateColor,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                'VOICE STATE: ${voiceState.toUpperCase()}',
                style: TextStyle(
                  color: stateColor,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Animated / simulated voice bars
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(9, (index) {
              final heights = [12.0, 24.0, 36.0, 48.0, 56.0, 44.0, 32.0, 20.0, 10.0];
              final isActive = voiceState == 'listening' || voiceState == 'speaking';
              final barHeight = isActive ? heights[index] : 6.0;

              return AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                margin: const EdgeInsets.symmetric(horizontal: 3),
                width: 5,
                height: barHeight,
                decoration: BoxDecoration(
                  color: stateColor,
                  borderRadius: BorderRadius.circular(4),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}
