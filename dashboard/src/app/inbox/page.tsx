import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { getInboxItems } from "@/lib/vault";

export const dynamic = "force-dynamic";

export default async function InboxPage() {
  const items = await getInboxItems();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Inbox</h2>
        <p className="text-muted-foreground">
          Incoming documents and Gmail events ({items.length} items)
        </p>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Preview</TableHead>
            <TableHead>Priority</TableHead>
            <TableHead>Timestamp</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                No items in inbox
              </TableCell>
            </TableRow>
          ) : (
            items.map((item) => (
              <TableRow key={item.name}>
                <TableCell className="font-mono text-sm">{item.name}</TableCell>
                <TableCell>
                  <Badge
                    variant={item.type === "gmail" ? "default" : "secondary"}
                  >
                    {item.type}
                  </Badge>
                </TableCell>
                <TableCell className="max-w-xs truncate">{item.preview}</TableCell>
                <TableCell>
                  {item.priority && (
                    <Badge
                      variant={
                        item.priority === "high"
                          ? "destructive"
                          : item.priority === "medium"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {item.priority}
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(item.timestamp).toLocaleString()}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
