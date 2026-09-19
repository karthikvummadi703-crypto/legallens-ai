import React, { useState, useRef } from 'react';
import { 
  UploadCloud, 
  FileText, 
  CheckCircle2, 
  Loader2, 
  Sparkles, 
  AlertCircle,
  FileCheck,
  Cpu,
  Brain,
  Layers,
  X
} from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { LegalDocument } from '../../types';
import { documentService } from '../../services/documentService';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadComplete: (doc: LegalDocument) => void;
}

type ProcessingStep = 'idle' | 'uploading' | 'extracting' | 'understanding' | 'analyzing' | 'preparing' | 'completed';

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadComplete
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processingStep, setProcessingStep] = useState<ProcessingStep>('idle');
  const [progressPercent, setProgressPercent] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const stepsList = [
    { key: 'uploading', label: 'Uploading document secure buffer...', icon: UploadCloud },
    { key: 'extracting', label: 'Extracting text & OCR layout parsing...', icon: FileCheck },
    { key: 'understanding', label: 'Understanding document architecture & structure...', icon: Cpu },
    { key: 'analyzing', label: 'Analyzing clauses & evaluating potential risks...', icon: Brain },
    { key: 'preparing', label: 'Preparing insights, obligations & checklist...', icon: Layers },
  ];

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const validateAndSetFile = (file: File) => {
    setErrorMsg(null);
    const validExtensions = ['.pdf', '.docx', '.txt', '.md', '.markdown', '.csv', '.html', '.htm', '.log'];
    const hasValidExt = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    if (!hasValidExt) {
      setErrorMsg('Unsupported format. Please select a PDF, DOCX, TXT, MD, CSV, HTML or LOG file.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setErrorMsg('File size exceeds the 20MB limit.');
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const startAnalysisPipeline = async () => {
    if (!selectedFile) return;

    setErrorMsg(null);
    setProcessingStep('uploading');
    setProgressPercent(15);

    // Fire the real upload immediately in parallel with the progress
    // animation, so large files don't sit through fake delays first and
    // failures surface with the server's actual reason.
    const uploadPromise = documentService.uploadDocument(selectedFile);

    try {
      // Step 1: Uploading
      await new Promise(r => setTimeout(r, 600));
      setProcessingStep('extracting');
      setProgressPercent(35);

      // Step 2: Extracting
      await new Promise(r => setTimeout(r, 700));
      setProcessingStep('understanding');
      setProgressPercent(60);

      // Step 3: Understanding
      await new Promise(r => setTimeout(r, 800));
      setProcessingStep('analyzing');
      setProgressPercent(85);

      // Await the real upload (already in flight); then finish animation.
      const uploadedDoc = await uploadPromise;
      setProcessingStep('preparing');
      setProgressPercent(98);

      await new Promise(r => setTimeout(r, 400));
      setProcessingStep('completed');
      setProgressPercent(100);

      setTimeout(() => {
        onUploadComplete(uploadedDoc);
        handleClose();
      }, 600);
    } catch (err) {
      const message = err instanceof Error && err.message
        ? err.message
        : 'Failed to process document. Please try again.';
      setErrorMsg(message);
      setProcessingStep('idle');
    }
  };

  const handleClose = () => {
    if (processingStep !== 'idle' && processingStep !== 'completed') {
      // Wait if analysis is still in progress
      return;
    }
    setSelectedFile(null);
    setProcessingStep('idle');
    setProgressPercent(0);
    setErrorMsg(null);
    onClose();
  };

  const isProcessing = processingStep !== 'idle' && processingStep !== 'completed';

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Upload Legal Document"
      description="Upload your contract or agreement for instant AI clause extraction and risk analysis."
      maxWidth="lg"
    >
      <div className="space-y-6 pt-2">
        {errorMsg && (
          <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Processing State View */}
        {isProcessing || processingStep === 'completed' ? (
          <div className="p-6 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-6">
            <div className="text-center space-y-2">
              <div className="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 mx-auto">
                {processingStep === 'completed' ? (
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 animate-in zoom-in-50" />
                ) : (
                  <Brain className="w-8 h-8 text-indigo-400 animate-pulse" />
                )}
                <div className="absolute inset-0 rounded-2xl bg-indigo-500/20 blur-xl -z-10" />
              </div>
              <h4 className="text-base font-semibold text-white tracking-tight">
                {processingStep === 'completed' ? 'Analysis Complete!' : 'Processing Legal Document'}
              </h4>
              <p className="text-xs text-slate-400">
                {selectedFile?.name} • {(selectedFile ? (selectedFile.size / (1024 * 1024)).toFixed(2) : 0)} MB
              </p>
            </div>

            {/* Progress Bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-indigo-300 font-mono text-[11px] font-medium">
                  {progressPercent}% Complete
                </span>
                <span className="text-slate-400 text-[11px]">
                  {processingStep === 'completed' ? 'Ready for review' : 'Running intelligence pipeline...'}
                </span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden p-0.5">
                <div 
                  className="h-full bg-gradient-to-r from-indigo-500 via-sky-400 to-violet-500 rounded-full transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>

            {/* Step Checkpoints */}
            <div className="space-y-2.5 pt-2">
              {stepsList.map((step, idx) => {
                const stepOrder = ['uploading', 'extracting', 'understanding', 'analyzing', 'preparing', 'completed'];
                const currentIdx = stepOrder.indexOf(processingStep);
                const stepIdx = stepOrder.indexOf(step.key);
                const isDone = currentIdx > stepIdx || processingStep === 'completed';
                const isCurrent = currentIdx === stepIdx;

                const StepIcon = step.icon;

                return (
                  <div 
                    key={step.key}
                    className={`flex items-center justify-between p-2.5 rounded-lg text-xs transition-colors ${
                      isCurrent ? 'bg-indigo-950/40 text-indigo-200 border border-indigo-500/30' :
                      isDone ? 'text-slate-300 bg-slate-900/40' : 'text-slate-500'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <StepIcon className={`w-4 h-4 ${isCurrent ? 'text-indigo-400 animate-spin' : isDone ? 'text-emerald-400' : 'text-slate-600'}`} />
                      <span>{step.label}</span>
                    </div>

                    {isDone && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
                    {isCurrent && <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin shrink-0" />}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Dropzone View */
          <div className="space-y-4">
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`relative border-2 border-dashed rounded-2xl p-8 sm:p-10 text-center transition-all duration-200 cursor-pointer flex flex-col items-center justify-center gap-3 ${
                dragActive 
                  ? 'border-indigo-400 bg-indigo-950/30 scale-[1.01]' 
                  : selectedFile 
                    ? 'border-indigo-500/60 bg-indigo-950/20' 
                    : 'border-slate-700/80 hover:border-indigo-500/50 hover:bg-slate-900/50 bg-slate-950/40'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.md,.markdown,.csv,.html,.htm,.log"
                onChange={handleFileChange}
                className="hidden"
              />

              <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-1">
                <UploadCloud className="w-8 h-8" />
              </div>

              <div className="space-y-1">
                <h4 className="text-base font-semibold text-white tracking-tight">
                  {selectedFile ? selectedFile.name : 'Drop your legal document here'}
                </h4>
                <p className="text-xs text-slate-400">
                  {selectedFile 
                    ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Click to replace file` 
                    : 'PDF, DOCX, TXT, MD, CSV, HTML or LOG up to 20MB'}
                </p>
              </div>

              {selectedFile ? (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-xs font-medium mt-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Ready to analyze
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  className="mt-2 text-xs"
                >
                  Browse Files
                </Button>
              )}
            </div>


          </div>
        )}

        {/* Action Buttons */}
        {!isProcessing && processingStep !== 'completed' && (
          <div className="flex items-center justify-end gap-3 pt-2">
            <Button
              variant="ghost"
              onClick={handleClose}
              disabled={isProcessing}
            >
              Cancel
            </Button>
            <Button
              variant="glow"
              disabled={!selectedFile || isProcessing}
              onClick={startAnalysisPipeline}
              rightIcon={<Sparkles className="w-4 h-4" />}
            >
              Add Document & Analyze
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
};
