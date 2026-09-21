import 'package:flutter/material.dart';
import 'voice_waveform_widget.dart';
import 'voice_controls_widget.dart';
import 'voice_transcript_widget.dart';

class VoiceAssistantView extends StatefulWidget {
  const VoiceAssistantView({super.key});

  @override
  State<VoiceAssistantView> createState() => _VoiceAssistantViewState();
}

class _VoiceAssistantViewState extends State<VoiceAssistantView> {
  String _voiceState = 'idle';
  bool _isMuted = false;
  List<Map<String, dynamic>> _messages = [];

  void _handleToggleListen() {
    if (_voiceState == 'idle') {
      setState(() {
        _voiceState = 'listening';
      });

      // Simulate spoken voice turn
      Future.delayed(const Duration(milliseconds: 1000), () {
        if (!mounted || _voiceState != 'listening') return;
        setState(() {
          _voiceState = 'transcribing';
        });

        Future.delayed(const Duration(milliseconds: 600), () {
          if (!mounted) return;
          setState(() {
            _messages.add({
              'role': 'user',
              'text': 'What tasks are scheduled for today in my workspace?',
            });
            _voiceState = 'thinking';
          });

          Future.delayed(const Duration(milliseconds: 800), () {
            if (!mounted) return;
            setState(() {
              _voiceState = 'speaking';
              _messages.add({
                'role': 'agent',
                'text': 'You have 3 active tasks scheduled: code indexing, repository sync, and unit test verification.',
              });
            });

            Future.delayed(const Duration(milliseconds: 1500), () {
              if (!mounted || _voiceState != 'speaking') return;
              setState(() {
                _voiceState = 'idle';
              });
            });
          });
        });
      });
    } else {
      setState(() {
        _voiceState = 'idle';
      });
    }
  }

  void _handleToggleMute() {
    setState(() {
      _isMuted = !_isMuted;
    });
  }

  void _handleInterrupt() {
    setState(() {
      _voiceState = 'interrupted';
    });
    Future.delayed(const Duration(milliseconds: 300), () {
      if (!mounted) return;
      setState(() {
        _voiceState = 'listening';
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Real-Time Voice Assistant'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            // Waveform & State Visualizer
            VoiceWaveformWidget(
              voiceState: _voiceState,
              isMuted: _isMuted,
            ),
            const SizedBox(height: 24),
            // Live Transcript Box
            Expanded(
              child: Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(
                    color: Theme.of(context).colorScheme.outlineVariant,
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: VoiceTranscriptWidget(messages: _messages),
                ),
              ),
            ),
            const SizedBox(height: 24),
            // Bottom Voice Controls
            VoiceControlsWidget(
              isListening: _voiceState == 'listening',
              isMuted: _isMuted,
              isSpeaking: _voiceState == 'speaking',
              onToggleListen: _handleToggleListen,
              onToggleMute: _handleToggleMute,
              onInterrupt: _handleInterrupt,
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }
}
