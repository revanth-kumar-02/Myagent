import 'package:flutter/material.dart';
import '../models/observability_models.dart';
import 'widgets/timeline_widget.dart';

class ObservabilityDashboardView extends StatefulWidget {
  const ObservabilityDashboardView({super.key});

  @override
  State<ObservabilityDashboardView> createState() => _ObservabilityDashboardViewState();
}

class _ObservabilityDashboardViewState extends State<ObservabilityDashboardView> {
  int _selectedTab = 0;
  TraceItem? _selectedTrace;

  final List<TraceItem> _dummyTraces = [
    TraceItem(
      traceId: 'trace-101-auth-flow',
      state: 'completed',
      model: 'qwen-chat',
      durationMs: 340,
      finalStatus: 'success',
      verificationResult: 'pass',
      createdAt: DateTime.now().subtract(const Duration(minutes: 5)),
      events: [
        EventItem(
          eventId: 'ev-1',
          eventType: 'request_received',
          component: 'agent_core',
          status: 'info',
          durationMs: 5,
          payload: {'intent': 'knowledge_rag'},
          timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
        EventItem(
          eventId: 'ev-2',
          eventType: 'context_retrieved',
          component: 'rag',
          status: 'success',
          durationMs: 45,
          payload: {'chunks_retrieved': 4, 'sources': ['session.py', 'auth.py']},
          timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
        EventItem(
          eventId: 'ev-3',
          eventType: 'tool_completed',
          component: 'tools',
          status: 'success',
          durationMs: 120,
          payload: {'tool': 'file_reader', 'file': 'auth.py'},
          timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
        EventItem(
          eventId: 'ev-4',
          eventType: 'task_completed',
          component: 'agent_core',
          status: 'success',
          durationMs: 170,
          payload: {'verification': 'pass'},
          timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
      ],
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Kora Observability & Agent Replay'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {},
            tooltip: 'Refresh Telemetry',
          ),
        ],
      ),
      body: Row(
        children: [
          // Left Sidebar: Active & Recent Traces
          SizedBox(
            width: 320,
            child: Container(
              decoration: BoxDecoration(
                border: Border(right: BorderSide(color: Colors.grey.shade300)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.all(12.0),
                    child: Text(
                      'Execution Traces',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                    ),
                  ),
                  const Divider(height: 1),
                  Expanded(
                    child: ListView.builder(
                      itemCount: _dummyTraces.length,
                      itemBuilder: (context, index) {
                        final trace = _dummyTraces[index];
                        final isSelected = _selectedTrace?.traceId == trace.traceId;
                        return ListTile(
                          selected: isSelected,
                          leading: Icon(
                            trace.finalStatus == 'success' ? Icons.check_circle : Icons.error,
                            color: trace.finalStatus == 'success' ? Colors.green : Colors.red,
                          ),
                          title: Text(
                            trace.traceId,
                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(
                            '${trace.durationMs}ms • ${trace.model ?? 'default'}',
                            style: const TextStyle(fontSize: 11),
                          ),
                          onTap: () {
                            setState(() {
                              _selectedTrace = trace;
                            });
                          },
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
          // Main Content Area: Replay Timeline & Metrics
          Expanded(
            child: Column(
              children: [
                // Top Tab Bar
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  color: Colors.grey.shade100,
                  child: Row(
                    children: [
                      _buildTabButton('Timeline & Replay', 0),
                      const SizedBox(width: 8),
                      _buildTabButton('System Health', 1),
                      const SizedBox(width: 8),
                      _buildTabButton('Error Center', 2),
                    ],
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: _buildTabContent(),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTabButton(String title, int index) {
    final isSelected = _selectedTab == index;
    return ElevatedButton(
      style: ElevatedButton.styleFrom(
        backgroundColor: isSelected ? Colors.blue : Colors.white,
        foregroundColor: isSelected ? Colors.white : Colors.black87,
        elevation: isSelected ? 2 : 0,
      ),
      onPressed: () {
        setState(() {
          _selectedTab = index;
        });
      },
      child: Text(title),
    );
  }

  Widget _buildTabContent() {
    if (_selectedTab == 0) {
      final activeTrace = _selectedTrace ?? (_dummyTraces.isNotEmpty ? _dummyTraces.first : null);
      if (activeTrace == null) {
        return const Center(child: Text('Select a trace to view timeline.'));
      }
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Trace: ${activeTrace.traceId}',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              Chip(
                label: Text(
                  activeTrace.finalStatus.toUpperCase(),
                  style: const TextStyle(color: Colors.white, fontSize: 11),
                ),
                backgroundColor: activeTrace.finalStatus == 'success' ? Colors.green : Colors.red,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Expanded(
            child: ExecutionTimelineWidget(events: activeTrace.events),
          ),
        ],
      );
    } else if (_selectedTab == 1) {
      return const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'System Subsystem Health',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          SizedBox(height: 12),
          ListTile(
            leading: Icon(Icons.check_circle, color: Colors.green),
            title: Text('PostgreSQL Database'),
            subtitle: Text('Healthy • Latency: 2ms'),
          ),
          ListTile(
            leading: Icon(Icons.check_circle, color: Colors.green),
            title: Text('RAG Embedding Pipeline'),
            subtitle: Text('Healthy • 1024-dim Vector Engine Ready'),
          ),
          ListTile(
            leading: Icon(Icons.check_circle, color: Colors.green),
            title: Text('DuckDuckGo Web Research'),
            subtitle: Text('Healthy • Web Provider Online'),
          ),
        ],
      );
    } else {
      return const Center(
        child: Text('No active critical errors detected in current session.'),
      );
    }
  }
}
