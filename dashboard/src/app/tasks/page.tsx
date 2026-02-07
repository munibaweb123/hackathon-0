import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getInboxItems, getProcessingFiles, getCompletedFiles } from "@/lib/vault";

export const dynamic = "force-dynamic";

export default async function TasksPage() {
  const [inboxItems, processing, completed] = await Promise.all([
    getInboxItems(),
    getProcessingFiles(),
    getCompletedFiles(),
  ]);

  const newFiles = inboxItems.filter((i) => i.type === "file");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Tasks</h2>
        <p className="text-muted-foreground">Workflow management and file processing status</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">New</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{newFiles.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Processing</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{processing.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{completed.length}</div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="new">
        <TabsList>
          <TabsTrigger value="new">New ({newFiles.length})</TabsTrigger>
          <TabsTrigger value="processing">Processing ({processing.length})</TabsTrigger>
          <TabsTrigger value="completed">Completed ({completed.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="new" className="space-y-2">
          {newFiles.length === 0 ? (
            <p className="py-4 text-muted-foreground">No new files</p>
          ) : (
            newFiles.map((f) => (
              <Card key={f.name}>
                <CardContent className="flex items-center justify-between py-3">
                  <span className="font-mono text-sm">{f.name}</span>
                  <Badge variant="secondary">New</Badge>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="processing" className="space-y-2">
          {processing.length === 0 ? (
            <p className="py-4 text-muted-foreground">No files processing</p>
          ) : (
            processing.map((f) => (
              <Card key={f}>
                <CardContent className="flex items-center justify-between py-3">
                  <span className="font-mono text-sm">{f}</span>
                  <Badge variant="default">Processing</Badge>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="completed" className="space-y-2">
          {completed.length === 0 ? (
            <p className="py-4 text-muted-foreground">No completed files</p>
          ) : (
            completed.map((f) => (
              <Card key={f}>
                <CardContent className="flex items-center justify-between py-3">
                  <span className="font-mono text-sm">{f}</span>
                  <Badge className="bg-green-600">Completed</Badge>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
