import { DocumentComparison } from '../types';

export const comparisonService = {
  async compareDocuments(_docAId: string, _docBId: string): Promise<DocumentComparison | null> {
    // No backend endpoint for comparison yet
    return null;
  }
};
