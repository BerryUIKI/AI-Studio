import React from 'react';
import { useNavigationStore, ViewType } from '../../stores/useNavigationStore';

interface ViewContainerProps {
  children: {
    [key in ViewType]?: React.ReactNode;
  };
}

export const ViewContainer: React.FC<ViewContainerProps> = ({ children }) => {
  const activeView = useNavigationStore((state) => state.activeView);

  return (
    <div className="flex-1 w-full h-full relative overflow-hidden bg-slate-950">
      <div key={activeView} id={`view-${activeView}`} className="absolute inset-0 w-full h-full z-10">
        {children[activeView]}
      </div>
    </div>
  );
};
