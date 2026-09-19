import React, { useState } from 'react';
import { 
  FileText, 
  Search, 
  Filter, 
  UploadCloud, 
  LayoutGrid, 
  List, 
  Trash2, 
  ArrowUpRight, 
  Calendar, 
  HardDrive,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { LegalDocument } from '../types';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { DocumentCard } from '../components/cards/DocumentCard';

interface DocumentsPageProps {
  documents: LegalDocument[];
  onSelectDocument: (doc: LegalDocument) => void;
  onAnalyze: (doc: LegalDocument) => void;
  onDeleteDocument: (id: string) => void;
  onOpenUpload: () => void;
}

export const DocumentsPage: React.FC<DocumentsPageProps> = ({
  documents,
  onSelectDocument,
  onAnalyze,
  onDeleteDocument,
  onOpenUpload
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');

  const categories = ['All', 'Employment', 'Real Estate', 'Corporate', 'Vendor & SaaS', 'Confidentiality'];

  const filteredDocs = (documents || []).filter((doc) => {
    if (!doc) return false;
    const matchesSearch = (doc.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (doc.summary || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'All' || doc.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div id="documents-management-page" className="p-4 sm:p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-['Space_Grotesk']">
            Your Documents
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Manage and review your uploaded legal documents.
          </p>
        </div>

        <Button
          variant="glow"
          size="md"
          onClick={onOpenUpload}
          leftIcon={<UploadCloud className="w-4 h-4" />}
        >
          Upload Document
        </Button>
      </div>

      {/* Filter & Search Bar */}
      <div className="p-4 rounded-2xl glass-panel border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by name, clause, or keywords..."
            className="w-full pl-9 pr-4 py-2 text-xs rounded-xl glass-input"
          />
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all whitespace-nowrap cursor-pointer hover-float-pill ${
                selectedCategory === cat
                  ? 'bg-indigo-600/25 text-indigo-300 border border-indigo-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60 border border-transparent hover:border-slate-800'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* View Mode Toggle (Grid vs Table) */}
        <div className="hidden sm:flex items-center gap-1 p-1 rounded-xl bg-slate-900 border border-slate-800 shrink-0">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-1.5 rounded-lg transition-colors ${
              viewMode === 'grid' ? 'bg-slate-800 text-white' : 'text-slate-500 hover:text-slate-300'
            }`}
            title="Grid view"
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('table')}
            className={`p-1.5 rounded-lg transition-colors ${
              viewMode === 'table' ? 'bg-slate-800 text-white' : 'text-slate-500 hover:text-slate-300'
            }`}
            title="Table view"
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Document Items View */}
      {filteredDocs.length === 0 ? (
        <div className="text-center py-16 p-8 rounded-3xl glass-panel border border-slate-800 space-y-3">
          <FileText className="w-12 h-12 text-slate-600 mx-auto" />
          <h3 className="text-base font-semibold text-white">No documents found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            No legal agreements match your current search query or category filter.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setSearchQuery('');
              setSelectedCategory('All');
            }}
          >
            Clear Filters
          </Button>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {filteredDocs.map((doc) => (
            <DocumentCard
              key={doc.id}
              document={doc}
              onSelect={onSelectDocument}
              onAnalyze={onAnalyze}
              onDelete={onDeleteDocument}
            />
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="rounded-2xl glass-panel border border-slate-800 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase font-mono text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4">Document Name</th>
                  <th className="py-3 px-4">Type / Pages</th>
                  <th className="py-3 px-4">Upload Date</th>
                  <th className="py-3 px-4">Attention Score</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredDocs.map((doc) => (
                  <tr 
                    key={doc.id} 
                    className="hover:bg-slate-850/50 transition-colors group cursor-pointer"
                    onClick={() => onSelectDocument(doc)}
                  >
                    <td className="py-3.5 px-4 font-semibold text-white">
                      <div className="flex items-center gap-2.5">
                        <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
                        <span className="truncate max-w-xs">{doc.name}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-400 font-mono">
                      {doc.type} • {doc.pageCount}p ({doc.size})
                    </td>
                    <td className="py-3.5 px-4 text-slate-400">
                      {doc.uploadDate}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`font-mono font-bold ${
                        doc.attentionScore >= 80 ? 'text-rose-400' :
                        doc.attentionScore >= 60 ? 'text-amber-400' : 'text-emerald-400'
                      }`}>
                        {doc.attentionScore}/100
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge variant={doc.analysisStatus} size="sm">
                        {doc.analysisStatus}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => onAnalyze(doc)}
                          className="text-xs py-1 h-auto"
                        >
                          Analyze
                        </Button>
                        <button
                          onClick={() => onDeleteDocument(doc.id)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
