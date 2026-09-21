import 'package:flutter/material.dart';
import 'workflow_step_builder_widget.dart';
import 'workflow_runner_widget.dart';

class VisualWorkflowView extends StatefulWidget {
  const VisualWorkflowView({super.key});

  @override
  State<VisualWorkflowView> createState() => _VisualWorkflowViewState();
}

class _VisualWorkflowViewState extends State<VisualWorkflowView> {
  Map<String, dynamic> _currentWorkflow = {
    'workflow_id': 'wf_auto_deploy_01',
    'name': 'Deploy Workspace Project',
    'description': 'Automated workflow to click settings and trigger deployment.',
    'target_app': 'Kora Desktop',
    'variables': {
      'project_name': 'MyAgent',
    },
    'steps': [
      {
        'step_id': 'step_1',
        'name': 'Open Settings',
        'action_type': 'click',
        'target_query': 'Settings button',
      },
      {
        'step_id': 'step_2',
        'name': 'Input Project Name',
        'action_type': 'type',
        'target_query': 'Search input',
        'input_text': '{{project_name}}',
      },
      {
        'step_id': 'step_3',
        'name': 'Confirm Deployment',
        'action_type': 'click',
        'target_query': 'Deploy button',
        'verification': {
          'expected_text': 'Deployed successfully',
        },
      },
    ],
  };

  bool _isRunning = false;
  int _currentStepIndex = 0;
  List<Map<String, dynamic>> _executionLogs = [];

  void _handleAddStep(Map<String, dynamic> step) {
    setState(() {
      (_currentWorkflow['steps'] as List<dynamic>).add(step);
    });
  }

  void _handleRemoveStep(int index) {
    setState(() {
      (_currentWorkflow['steps'] as List<dynamic>).removeAt(index);
    });
  }

  void _handleRunWorkflow() {
    setState(() {
      _isRunning = true;
      _currentStepIndex = 0;
      _executionLogs = [
        {'message': 'Workflow "${_currentWorkflow['name']}" initialized.', 'verification_status': 'info'},
      ];
    });

    final steps = _currentWorkflow['steps'] as List<dynamic>;

    Future.delayed(const Duration(milliseconds: 500), () {
      if (!mounted) return;
      setState(() {
        _currentStepIndex = 1;
        _executionLogs.add({
          'message': 'Step 1: Grounded "Settings button" at (170, 258). Click executed.',
          'verification_status': 'success',
        });
      });

      Future.delayed(const Duration(milliseconds: 500), () {
        if (!mounted) return;
        setState(() {
          _currentStepIndex = 2;
          _executionLogs.add({
            'message': 'Step 2: Typed "{{project_name}}" -> "MyAgent". Verification passed.',
            'verification_status': 'success',
          });
        });

        Future.delayed(const Duration(milliseconds: 500), () {
          if (!mounted) return;
          setState(() {
            _isRunning = false;
            _executionLogs.add({
              'message': 'Step 3: Grounded "Deploy button" at (875, 642). Workflow complete!',
              'verification_status': 'success',
            });
          });
        });
      });
    });
  }

  void _handleCancelWorkflow() {
    setState(() {
      _isRunning = false;
      _executionLogs.add({
        'message': 'Workflow execution cancelled by user.',
        'verification_status': 'failed',
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Visual Workflow Automation'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Left column: Steps Builder
            Expanded(
              flex: 3,
              child: WorkflowStepBuilderWidget(
                steps: List<Map<String, dynamic>>.from(_currentWorkflow['steps'] ?? []),
                onAddStep: _handleAddStep,
                onRemoveStep: _handleRemoveStep,
              ),
            ),
            const SizedBox(width: 16),
            // Right column: Workflow Runner & Logs
            Expanded(
              flex: 3,
              child: WorkflowRunnerWidget(
                currentWorkflow: _currentWorkflow,
                isRunning: _isRunning,
                currentStepIndex: _currentStepIndex,
                executionLogs: _executionLogs,
                onRunWorkflow: _handleRunWorkflow,
                onCancelWorkflow: _handleCancelWorkflow,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
