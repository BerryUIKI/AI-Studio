import React from 'react';
import { useNavigationStore, ViewType } from '../../stores/useNavigationStore';

interface ViewContainerProps {
  children: {
    [key in ViewType]?: React.ReactNode;
  };
}

export const ViewContainer: React.FC<ViewContainerProps> = ({ children }) => {
  const { activeView } = useNavigationStore();

  return (
    <div className="flex-1 w-full h-full relative overflow-hidden bg-slate-950">
      {(Object.keys(children) as ViewType[]).map((viewKey) => {
        const isActive = activeView === viewKey;
        const viewContent = children[viewKey];

        if (!viewContent) return null;

        return (
          <div
            key={viewKey}
            id={`view-${viewKey}`}
            className={`absolute inset-0 w-full h-full ${
              isActive ? 'block z-10' : 'hidden pointer-events-none'
            }`}
            aria-hidden={!isActive}
          >
            {viewContent}
          </div>
        );
      })}
    </div>
  );
};
