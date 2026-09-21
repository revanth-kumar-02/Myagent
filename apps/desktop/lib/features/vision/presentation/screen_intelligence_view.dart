import 'package:flutter/material.dart';
import 'screen_preview_widget.dart';
import 'detected_elements_widget.dart';
import 'visual_action_history_widget.dart';

class ScreenIntelligenceView extends StatefulWidget {
  const ScreenIntelligenceView({super.key});

  @override
  State<ScreenIntelligenceView> createState() => _ScreenIntelligenceViewState();
}

class _ScreenIntelligenceViewState extends State<ScreenIntelligenceView> {
  String? _currentScreenshotPath;
  List<Map<String, dynamic>> _detectedElements = [];
  Map<String, dynamic>? _activeTarget;
  List<Map<String, dynamic>> _actionHistory = [];
  bool _isAnalyzing = false;

  void _handleCaptureScreen() {
    setState(() {
      _isAnalyzing = true;
    });

    // Simulated visual capture and detection flow
    Future.delayed(const Duration(milliseconds: 600), () {
      if (!mounted) return;
      setState(() {
        _isAnalyzing = false;
        _currentScreenshotPath = '/tmp/kora_vision/cap_live_01.png';
        _detectedElements = [
          {
            'id': 'el_btn_settings',
            'element_type': 'button',
            'label': 'Settings',
            'confidence': 0.98,
            'bounding_box': {
              'x': 120,
              'y': 240,
              'width': 100,
              'height': 36,
              'center': [170, 258],
            },
          },
          {
            'id': 'el_inp_search',
            'element_type': 'input_field',
            'label': 'Search Repositories',
            'confidence': 0.95,
            'bounding_box': {
              'x': 320,
              'y': 140,
              'width': 280,
              'height': 40,
              'center': [460, 160],
            },
          },
          {
            'id': 'el_btn_submit',
            'element_type': 'button',
            'label': 'Deploy Changes',
            'confidence': 0.99,
            'bounding_box': {
              'x': 800,
              'y': 620,
              'width': 150,
              'height': 44,
              'center': [875, 642],
            },
          },
        ];
      });
    });
  }

  void _handleElementSelected(Map<String, dynamic> element) {
    final bbox = element['bounding_box'] as Map<String, dynamic>? ?? {};
    final center = bbox['center'] as List<dynamic>? ?? [0, 0];

    setState(() {
      _activeTarget = {
        'x': center[0],
        'y': center[1],
        'label': element['label'],
      };

      _actionHistory.insert(0, {
        'action_type': 'click',
        'target_label': element['label'],
        'coordinates': center,
        'verification_status': 'success',
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Computer Vision & Screen Intelligence'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh Screen',
            onPressed: _handleCaptureScreen,
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Left column: Screen Canvas Preview
            Expanded(
              flex: 3,
              child: ScreenPreviewWidget(
                screenshotPath: _currentScreenshotPath,
                detectedElements: _detectedElements,
                activeTarget: _activeTarget,
                isAnalyzing: _isAnalyzing,
                onRefreshCapture: _handleCaptureScreen,
              ),
            ),
            const SizedBox(width: 16),
            // Right column: Detected Elements & Action History
            Expanded(
              flex: 2,
              child: Column(
                children: [
                  Expanded(
                    flex: 3,
                    child: DetectedElementsWidget(
                      elements: _detectedElements,
                      onElementSelected: _handleElementSelected,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Expanded(
                    flex: 2,
                    child: VisualActionHistoryWidget(
                      actions: _actionHistory,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
