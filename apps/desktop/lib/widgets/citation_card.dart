import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../core/theme/app_theme.dart';
import '../models/citation.dart';

class CitationCard extends StatelessWidget {
  final List<RagSource> sources;
  final List<WebSource> webSources;

  const CitationCard({
    super.key,
    this.sources = const [],
    this.webSources = const [],
  });

  @override
  Widget build(BuildContext context) {
    if (sources.isEmpty && webSources.isEmpty) return const SizedBox.shrink();

    final c = AppTheme.colors(context);

    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.border, width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.02),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.verified_rounded, size: 15, color: c.primary),
              const SizedBox(width: 8),
              Text(
                'Sources & Evidence (${sources.length + webSources.length})',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: c.textPrimary,
                ),
              ),
              const Spacer(),
              Text(
                'Context Citations',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: c.textMuted,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          // Bento Grid of Citations
          LayoutBuilder(
            builder: (context, constraints) {
              return Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  ...sources.map((src) => Container(
                    constraints: const BoxConstraints(minWidth: 160, maxWidth: 240),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: c.surfaceHighlight.withValues(alpha: 0.6),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: c.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              width: 24,
                              height: 24,
                              decoration: BoxDecoration(
                                color: c.primaryLight,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Icon(Icons.description_rounded, size: 13, color: c.primary),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                src.filePath,
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: c.textPrimary,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              src.startLine != null ? 'L${src.startLine}-L${src.endLine}' : 'Workspace',
                              style: TextStyle(fontSize: 10, color: c.textMuted, fontFamily: 'monospace'),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                              decoration: BoxDecoration(
                                color: c.primaryLight,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                'RAG Match',
                                style: TextStyle(
                                  fontSize: 9.5,
                                  fontWeight: FontWeight.w600,
                                  color: c.primaryDark,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  )),
                  ...webSources.map((web) => Container(
                    constraints: const BoxConstraints(minWidth: 160, maxWidth: 240),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: c.surfaceHighlight.withValues(alpha: 0.6),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: c.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              width: 24,
                              height: 24,
                              decoration: BoxDecoration(
                                color: c.accentLight,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Icon(Icons.public_rounded, size: 13, color: c.accent),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                web.title,
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: c.textPrimary,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Text(
                                web.url,
                                style: TextStyle(fontSize: 10, color: c.primary, decoration: TextDecoration.underline),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 4),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                              decoration: BoxDecoration(
                                color: c.accentLight,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                'Web',
                                style: TextStyle(
                                  fontSize: 9.5,
                                  fontWeight: FontWeight.w600,
                                  color: c.accent,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  )),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
