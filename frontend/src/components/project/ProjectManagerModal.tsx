import React, { useState } from 'react';
import {
  FolderOpen,
  Plus,
  Search,
  Trash2,
  Edit2,
  Check,
  X,
  Clock,
  Layers,
} from 'lucide-react';
import { useProjectStore } from '../../stores/useProjectStore';

export interface ProjectManagerModalProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const ProjectManagerModal: React.FC<ProjectManagerModalProps> = ({ isOpen, onClose }) => {
  const {
    currentProject,
    projects,
    isManagerModalOpen,
    setIsManagerModalOpen,
    createProject,
    openProject,
    renameProject,
    deleteProject,
  } = useProjectStore();

  const isModalOpen = isOpen !== undefined ? isOpen : isManagerModalOpen;

  const handleClose = () => {
    onClose?.();
    setIsManagerModalOpen(false);
  };

  const [searchQuery, setSearchQuery] = useState('');
  const [newProjectName, setNewProjectName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  if (!isModalOpen) return null;

  const filteredProjects = projects.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newProjectName.trim() || 'Untitled Project';
    await createProject(name);
    setNewProjectName('');
    setIsCreating(false);
    handleClose();
  };

  const handleStartRename = (id: string, currentName: string) => {
    setEditingId(id);
    setEditName(currentName);
  };

  const handleSaveRename = async (id: string) => {
    if (editName.trim()) {
      await renameProject(id, editName.trim());
    }
    setEditingId(null);
  };

  const handleDelete = async (id: string) => {
    await deleteProject(id);
    setConfirmDeleteId(null);
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm animate-fade-in"
      onClick={handleClose}
    >
      <div
        className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <FolderOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Project Library</h2>
              <p className="text-xs text-slate-400">Manage and switch between your durable creative canvases</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Toolbar & Search */}
        <div className="p-6 pb-2 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search projects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-slate-950/60 border border-slate-800 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            {!isCreating && (
              <button
                onClick={() => setIsCreating(true)}
                className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl flex items-center gap-1.5 transition shadow"
              >
                <Plus className="w-4 h-4" />
                <span>New Project</span>
              </button>
            )}
          </div>

          {/* Inline Create Form */}
          {isCreating && (
            <form onSubmit={handleCreate} className="flex items-center gap-2 p-3 bg-slate-950/50 border border-indigo-500/30 rounded-xl">
              <input
                type="text"
                placeholder="Project name..."
                autoFocus
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-750 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
              <button
                type="submit"
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition"
              >
                Create
              </button>
              <button
                type="button"
                onClick={() => setIsCreating(false)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
              >
                Cancel
              </button>
            </form>
          )}
        </div>

        {/* Project List */}
        <div className="flex-1 overflow-y-auto p-6 pt-3 space-y-2.5">
          {filteredProjects.length === 0 ? (
            <div className="py-12 text-center text-slate-500">
              <Layers className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No projects found</p>
            </div>
          ) : (
            filteredProjects.map((proj) => {
              const isActive = currentProject?.id === proj.id;
              const isEditing = editingId === proj.id;
              const isConfirmingDelete = confirmDeleteId === proj.id;
              const nodeCount = proj.canvas?.nodes?.length ?? 0;

              return (
                <div
                  key={proj.id}
                  className={`group flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                    isActive
                      ? 'bg-indigo-950/30 border-indigo-500/50 ring-1 ring-indigo-500/30'
                      : 'bg-slate-950/40 border-slate-800/80 hover:border-slate-700 hover:bg-slate-950/70'
                  }`}
                >
                  <div className="flex-1 min-w-0 pr-4">
                    {isEditing ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveRename(proj.id);
                            if (e.key === 'Escape') setEditingId(null);
                          }}
                          className="px-2 py-1 bg-slate-900 border border-indigo-500 rounded text-sm text-slate-100 focus:outline-none"
                        />
                        <button
                          onClick={() => handleSaveRename(proj.id)}
                          className="p-1 text-emerald-400 hover:bg-slate-800 rounded"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="p-1 text-slate-400 hover:bg-slate-800 rounded"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm text-slate-200 truncate">{proj.name}</span>
                        {isActive && (
                          <span className="px-2 py-0.5 text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded-full">
                            Active
                          </span>
                        )}
                        <span className="text-[10px] font-mono text-slate-500">v{proj.version || 1}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 font-mono">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(proj.updated_at)}
                      </span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Layers className="w-3 h-3" />
                        {nodeCount} items
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {isConfirmingDelete ? (
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-rose-400">Delete?</span>
                        <button
                          onClick={() => handleDelete(proj.id)}
                          className="px-2 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded text-xs font-medium"
                        >
                          Yes
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs"
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <>
                        {!isActive && (
                          <button
                            onClick={async () => {
                              await openProject(proj.id);
                              handleClose();
                            }}
                            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition"
                          >
                            Open
                          </button>
                        )}
                        <button
                          onClick={() => handleStartRename(proj.id, proj.name)}
                          className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
                          title="Rename"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(proj.id)}
                          className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition"
                          title="Delete project"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
