import 'dart:html' as html;
import 'dart:ui_web' as ui_web;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:file_picker/file_picker.dart';

import '../theme.dart';
import '../constants.dart';
import '../models/models.dart';
import '../providers/providers.dart';

class UploadCard extends ConsumerWidget {
  const UploadCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final uploadState = ref.watch(uploadProgressProvider);

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.lightGray,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.gray.withOpacity(0.3), width: 1),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Upload Document',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            'Support PDF format files',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          InkWell(
            onTap: uploadState.status == UploadStatus.uploading
                ? null
                : () async {
                    final result = await FilePicker.platform.pickFiles(
                      type: FileType.custom,
                      allowedExtensions: ['pdf'],
                      withData: true,
                    );
                    if (result != null && result.files.isNotEmpty) {
                      final file = result.files.first;
                      ref.read(uploadProgressProvider.notifier).uploadFile(file, ref);
                    }
                  },
            borderRadius: AppTheme.pShapeRadiusCustom(8),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: AppTheme.pShapeRadiusCustom(8),
                border: Border.all(
                  color: AppTheme.primaryBlue.withOpacity(0.3),
                  width: 1.5,
                  style: BorderStyle.solid,
                ),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.cloud_upload_rounded,
                    size: 40,
                    color: AppTheme.primaryBlue,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Click to select PDF document',
                    style: GoogleFonts.barlow(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primaryBlue,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'PDF file up to 20MB',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
          if (uploadState.status == UploadStatus.uploading) ...[
            const SizedBox(height: 12),
            const LinearProgressIndicator(
              backgroundColor: Colors.white,
              valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
            ),
            const SizedBox(height: 8),
            Center(
              child: Text(
                'Uploading document...',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.primaryBlue,
                    ),
              ),
            ),
          ],
          if (uploadState.status == UploadStatus.success) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.accentGreen.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Row(
                children: [
                  const Icon(Icons.check_circle_rounded, color: AppTheme.accentGreen, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      uploadState.message ?? 'Uploaded successfully!',
                      style: GoogleFonts.barlow(
                        fontSize: 13,
                        color: AppTheme.accentGreen,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (uploadState.status == UploadStatus.error) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.accentRed.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_rounded, color: AppTheme.accentRed, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      uploadState.message ?? 'Upload failed.',
                      style: GoogleFonts.barlow(
                        fontSize: 13,
                        color: AppTheme.accentRed,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class DocumentListCard extends ConsumerWidget {
  final PDFFile? selectedFile;

  const DocumentListCard({super.key, required this.selectedFile});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fileListState = ref.watch(fileListProvider);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Uploaded PDFs',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                ),
                Text(
                  '${fileListState.files.length} items',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const Divider(height: 1, color: AppTheme.lightGray),
          Expanded(
            child: fileListState.isLoading
                ? const Center(
                    child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
                    ),
                  )
                : fileListState.error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.error_outline_rounded, color: AppTheme.accentRed, size: 32),
                              const SizedBox(height: 8),
                              Text(
                                'Error loading files',
                                style: GoogleFonts.barlow(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                fileListState.error!,
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      )
                    : fileListState.files.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(32.0),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.picture_as_pdf_outlined, color: AppTheme.gray.withOpacity(0.5), size: 48),
                                  const SizedBox(height: 12),
                                  Text(
                                    'No documents uploaded yet',
                                    textAlign: TextAlign.center,
                                    style: GoogleFonts.barlow(
                                      color: AppTheme.gray,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          )
                        : ListView.separated(
                            itemCount: fileListState.files.length,
                            separatorBuilder: (context, index) => const Divider(height: 1, color: AppTheme.lightGray),
                            itemBuilder: (context, index) {
                              final file = fileListState.files[index];
                              final isSelected = selectedFile?.filename == file.filename;

                              return Material(
                                color: Colors.transparent,
                                child: ListTile(
                                  selected: isSelected,
                                  selectedTileColor: AppTheme.primaryBlue.withOpacity(0.05),
                                  leading: Icon(
                                    Icons.picture_as_pdf,
                                    color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
                                  ),
                                  title: Text(
                                    file.filename,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: GoogleFonts.barlow(
                                      fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                                      color: isSelected ? AppTheme.primaryBlue : AppTheme.textBlack,
                                    ),
                                  ),
                                  subtitle: Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        file.formattedSize,
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                      Text(
                                        file.formattedDate,
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                    ],
                                  ),
                                  onTap: () {
                                    ref.read(selectedFileProvider.notifier).state = file;
                                  },
                                ),
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}

class PDFViewerCard extends ConsumerWidget {
  final PDFFile? selectedFile;

  const PDFViewerCard({super.key, required this.selectedFile});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (selectedFile == null) {
      return Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
        ),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.folder_open_rounded,
                size: 64,
                color: AppTheme.gray.withOpacity(0.4),
              ),
              const SizedBox(height: 16),
              Text(
                'No Document Selected',
                style: GoogleFonts.inter(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Upload a PDF document or select one from the list to view it.',
                style: GoogleFonts.barlow(
                  fontSize: 14,
                  color: AppTheme.gray,
                ),
              ),
            ],
          ),
        ),
      );
    }

    final fileUrl = AppConstants.viewFileUrl(selectedFile!.filename);

    if (kIsWeb) {
      final String viewId = 'pdf-viewer-${selectedFile!.filename.hashCode}';
      ui_web.platformViewRegistry.registerViewFactory(
        viewId,
        (int id) => html.IFrameElement()
          ..src = fileUrl
          ..style.border = 'none'
          ..style.width = '100%'
          ..style.height = '100%',
      );

      return Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: AppTheme.lightGray,
              child: Row(
                children: [
                  const Icon(Icons.picture_as_pdf, color: AppTheme.primaryBlue),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      selectedFile!.filename,
                      style: GoogleFonts.barlow(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.auto_stories, size: 16),
                    label: const Text('Create Course'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      backgroundColor: AppTheme.primaryBlue,
                      shape: RoundedRectangleBorder(
                        borderRadius: AppTheme.pShapeRadiusCustom(6.0),
                      ),
                    ),
                    onPressed: () {
                      ref.read(courseGenerationProvider.notifier).generateCourse(selectedFile!.filename, ref);
                    },
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.open_in_new, color: AppTheme.primaryBlue, size: 20),
                    onPressed: () {
                      html.window.open(fileUrl, '_blank');
                    },
                    tooltip: 'Open in new tab',
                  ),
                ],
              ),
            ),
            Expanded(
              child: HtmlElementView(
                viewType: viewId,
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.picture_as_pdf, size: 64, color: AppTheme.primaryBlue),
            const SizedBox(height: 16),
            Text(
              'PDF viewer is running in Web mode.',
              style: GoogleFonts.barlow(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            TextButton.icon(
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open Document Link'),
              onPressed: () {
                debugPrint('Open URL: $fileUrl');
              },
            ),
          ],
        ),
      ),
    );
  }
}
